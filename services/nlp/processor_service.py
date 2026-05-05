import os
import json
import asyncio
from kafka import KafkaConsumer, KafkaProducer
from .controller import NLPController
import psycopg2
from datetime import datetime
import redis
import time
from kafka.errors import NoBrokersAvailable

class NLPProcessorService:
    def __init__(self):
        self.kafka_broker = os.getenv("KAFKA_BROKER", os.getenv("KAFKA_BROKER_URL", "localhost:29092"))
        self.raw_topic = os.getenv("RAW_TOPIC", "raw_posts")
        self.processed_topic = os.getenv("PROCESSED_TOPIC", "processed_signals")
        self.dlq_topic = os.getenv("DLQ_TOPIC", "raw_posts_dlq")
        self.db_url = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.controller = NLPController()
        
        self.consumer = self._connect_consumer_with_retry()
        self.producer = self._connect_producer_with_retry()
        
        self.db_conn = psycopg2.connect(self.db_url)
        try:
            self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, db=0)
        except Exception:
            self.redis_client = None

    def _connect_consumer_with_retry(self, retries=30, delay=3):
        for attempt in range(1, retries + 1):
            try:
                return KafkaConsumer(
                    self.raw_topic,
                    bootstrap_servers=self.kafka_broker,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    group_id="nlp_processors"
                )
            except NoBrokersAvailable:
                print(f"Kafka consumer connect failed (attempt {attempt}/{retries}). Retrying in {delay}s...")
                time.sleep(delay)
        raise NoBrokersAvailable()

    def _connect_producer_with_retry(self, retries=30, delay=3):
        for attempt in range(1, retries + 1):
            try:
                return KafkaProducer(
                    bootstrap_servers=self.kafka_broker,
                    value_serializer=lambda m: json.dumps(m).encode('utf-8')
                )
            except NoBrokersAvailable:
                print(f"Kafka producer connect failed (attempt {attempt}/{retries}). Retrying in {delay}s...")
                time.sleep(delay)
        raise NoBrokersAvailable()

    async def run(self):
        print(f"NLP Processor Service started. Listening on '{self.raw_topic}'...")
        for message in self.consumer:
            raw_post = message.value
            try:
                print(f"--- [NEW MESSAGE] Received post ID: {raw_post.get('id')} ---")
                
                # Run NLP Pipeline
                print("Running NLP pipeline...")
                result = await self.controller.process_text(raw_post.get("text", ""))
                print(f"Pipeline complete. Detected lang: {result['detected_lang']}")
                
                # Enrich and Save
                print("Saving to database...")
                self.save_to_db(raw_post, result)
                print("Successfully saved to DB.")
                self.producer.send(self.processed_topic, {
                    "post_id": raw_post.get("id"),
                    "detected_lang": result["detected_lang"],
                    "entities": result["entities"],
                    "district_id": raw_post.get("district_id"),
                    "posted_at": raw_post.get("posted_at")
                })
            except Exception as e:
                print(f"Pipeline error for post {raw_post.get('id')}: {e}")
                dlq_payload = {
                    "error": str(e),
                    "raw_post": raw_post,
                    "failed_at": datetime.now().isoformat()
                }
                self.producer.send(self.dlq_topic, dlq_payload)
                self._track_dlq(dlq_payload)

    def save_to_db(self, raw_post, nlp_result):
        cursor = self.db_conn.cursor()
        try:
            district_id = raw_post.get("district_id")
            lon = raw_post.get("lng")
            lat = raw_post.get("lat")
            if (lon is None or lat is None) and isinstance(raw_post.get("location"), dict):
                lon = raw_post["location"].get("lng", lon)
                lat = raw_post["location"].get("lat", lat)

            # If precise coordinates are not provided, fall back to district centroid.
            if district_id and (lon is None or lat is None):
                cursor.execute(
                    """
                    SELECT ST_X(ST_Centroid(geom)) AS lng, ST_Y(ST_Centroid(geom)) AS lat
                    FROM districts
                    WHERE id = %s AND geom IS NOT NULL
                    """,
                    (district_id,)
                )
                centroid = cursor.fetchone()
                if centroid:
                    lon = centroid[0]
                    lat = centroid[1]

            # 1. Update/Insert Post
            cursor.execute(
                """
                INSERT INTO posts (
                    platform, post_id_hash, text_cleaned, text_translated,
                    detected_lang, district_mapping_method, district_id, geom, posted_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    CASE
                        WHEN %s IS NOT NULL AND %s IS NOT NULL THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                        ELSE NULL
                    END,
                    %s
                )
                ON CONFLICT (platform, post_id_hash, posted_at) DO UPDATE SET
                    text_cleaned = EXCLUDED.text_cleaned,
                    text_translated = EXCLUDED.text_translated,
                    detected_lang = EXCLUDED.detected_lang,
                    district_mapping_method = COALESCE(EXCLUDED.district_mapping_method, posts.district_mapping_method),
                    district_id = COALESCE(EXCLUDED.district_id, posts.district_id),
                    geom = COALESCE(EXCLUDED.geom, posts.geom),
                    posted_at = EXCLUDED.posted_at
                RETURNING id
                """,
                (
                    raw_post.get("platform"),
                    raw_post.get("id_hash"),
                    raw_post.get("text"),
                    nlp_result["translated_text"],
                    nlp_result["detected_lang"],
                    raw_post.get("district_mapping_method"),
                    district_id,
                    lon, lat, lon, lat,
                    raw_post.get("posted_at", datetime.now().isoformat())
                )
            )
            post_uuid = cursor.fetchone()[0]
            
            # 2. Insert Entities
            for ent in nlp_result["entities"]:
                cursor.execute(
                    """
                    INSERT INTO post_entities (post_id, posted_at, entity_type, entity_text, ontology_code, ontology_system, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        post_uuid,
                        raw_post.get("posted_at", datetime.now().isoformat()),
                        ent["label"],
                        ent["text"],
                        ent["ontology_code"],
                        ent["ontology_system"],
                        ent["confidence"]
                    )
                )
            
            self.db_conn.commit()
        except Exception as e:
            print(f"DB Error: {e}")
            self.db_conn.rollback()
        finally:
            cursor.close()

    def _track_dlq(self, payload):
        if not self.redis_client:
            return
        try:
            self.redis_client.incr("dlq:total")
            self.redis_client.lpush("dlq:recent", json.dumps(payload))
            self.redis_client.ltrim("dlq:recent", 0, 99)
        except Exception:
            pass

if __name__ == "__main__":
    service = NLPProcessorService()
    asyncio.run(service.run())
