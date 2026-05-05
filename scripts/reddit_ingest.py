import hashlib
import json
import os
import time
import sys
from datetime import datetime, timezone

import praw
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.geospatial.district_mapper import DistrictMapper

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", os.getenv("KAFKA_BROKER_URL", "localhost:29092"))
TOPIC = os.getenv("RAW_TOPIC", "raw_posts")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "setu-aarogya-drishti/0.1")
INDIA_SUBREDDITS = os.getenv("INDIA_SUBREDDITS", "india,indiasocial")
MEDICAL_SUBREDDITS = os.getenv("MEDICAL_SUBREDDITS", "AskDocs,medical_advice")
REDDIT_KEYWORDS = [k.strip().lower() for k in os.getenv("REDDIT_KEYWORDS", "fever,cough,vomit,vomiting,dizzy,dizziness,paracetamol,coldrif,dolo").split(",") if k.strip()]
DEFAULT_DISTRICT_ID = int(os.getenv("DEFAULT_DISTRICT_ID", "1"))


def build_reddit_client():
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise RuntimeError("Missing REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET in environment.")
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        check_for_async=False,
    )


def build_producer(retries=30, delay=3):
    for attempt in range(1, retries + 1):
        try:
            return KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        except NoBrokersAvailable:
            print(f"Kafka producer connect failed (attempt {attempt}/{retries}). Retrying in {delay}s...")
            time.sleep(delay)
    raise NoBrokersAvailable()


def looks_health_related(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in REDDIT_KEYWORDS)


def to_message(post, platform="Reddit"):
    body = f"{post.title}\n{post.selftext}".strip() if hasattr(post, "title") else post.body.strip()
    created = datetime.fromtimestamp(post.created_utc, tz=timezone.utc).isoformat()
    post_id_hash = hashlib.sha256(f"{platform}:{post.id}".encode("utf-8")).hexdigest()
    return {
        "platform": platform,
        "id": f"{platform.lower()}_{post.id}",
        "id_hash": post_id_hash,
        "text": body,
        "posted_at": created,
        "district_id": DEFAULT_DISTRICT_ID,
        "source_url": f"https://reddit.com{post.permalink}",
    }


def run():
    print(f"Connecting Kafka producer to {KAFKA_BROKER} ...")
    producer = build_producer()
    reddit = build_reddit_client()
    mapper = DistrictMapper()

    india_list = [s.strip() for s in INDIA_SUBREDDITS.split(",") if s.strip()]
    medical_list = [s.strip() for s in MEDICAL_SUBREDDITS.split(",") if s.strip()]
    merged = list(dict.fromkeys(india_list + medical_list))
    subreddits = "+".join(merged)
    print(f"Streaming Reddit submissions from: {subreddits}")
    stream = reddit.subreddit(subreddits).stream.submissions(skip_existing=True)

    sent = 0
    while True:
        try:
            submission = next(stream)
            if submission is None:
                time.sleep(1)
                continue

            text = f"{submission.title}\n{submission.selftext}".strip()
            if not text or not looks_health_related(text):
                continue

            payload = to_message(submission, platform="Reddit")
            location = mapper.resolve(payload["text"])
            if location["district_id"] is None and DEFAULT_DISTRICT_ID:
                location = {"district_id": DEFAULT_DISTRICT_ID, "lat": None, "lng": None, "method": "default_fallback"}

            payload["district_id"] = location["district_id"]
            payload["lat"] = location["lat"]
            payload["lng"] = location["lng"]
            payload["district_mapping_method"] = location["method"]
            producer.send(TOPIC, payload)
            producer.flush()
            sent += 1
            print(f"[{sent}] sent {payload['id']} -> {TOPIC} (district_id={payload['district_id']}, method={payload['district_mapping_method']})")
        except Exception as exc:
            print(f"Reddit ingest loop error: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    run()
