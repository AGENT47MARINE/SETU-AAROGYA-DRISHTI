import json
import time
import os
from kafka import KafkaProducer
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:29092")
TOPIC = "raw_posts"

# Synthetic posts containing health signals
FIXTURE_POSTS = [
    {
        "platform": "X",
        "id": "sim_101",
        "id_hash": "hash_101",
        "text": "Paracetamol lene ke baad chakkar aa raha hai",
        "posted_at": datetime.utcnow().isoformat(),
        "district_id": 1 # Bhopal
    },
    {
        "platform": "Reddit",
        "id": "sim_102",
        "id_hash": "hash_102",
        "text": "My child had Coldrif syrup yesterday and now has severe stomach pain.",
        "posted_at": datetime.utcnow().isoformat(),
        "district_id": 1
    },
    {
        "platform": "Sharechat",
        "id": "sim_103",
        "id_hash": "hash_103",
        "text": "dolo 650 போட்ட பிறகு வாந்தி வருகிறது", # "Vomiting after taking dolo 650"
        "posted_at": datetime.utcnow().isoformat(),
        "district_id": 1
    }
]

def run_simulation(repeat=1, interval=1):
    print(f"Connecting to Kafka at {KAFKA_BROKER}...")
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        for i in range(repeat):
            for post in FIXTURE_POSTS:
                post["posted_at"] = datetime.utcnow().isoformat()
                post_id = f"{post['id']}_r{i}"
                post_to_send = post.copy()
                post_to_send["id"] = post_id
                producer.send(TOPIC, post_to_send)
                print(f"Sent post {post_id} to {TOPIC}")
                time.sleep(interval)

        producer.flush()
        print(f"Simulation complete. Sent {len(FIXTURE_POSTS) * repeat} posts.")
    except Exception as e:
        print(f"Failed to connect to Kafka or send messages: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1, help="Times to repeat fixture data")
    parser.add_argument("--interval", type=int, default=1, help="Seconds between posts")
    args = parser.parse_args()
    
    run_simulation(repeat=args.repeat, interval=args.interval)
