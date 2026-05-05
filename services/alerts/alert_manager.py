import os
import time
import json
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stats import compute_prr_ror_ic, rolling_zscore_spikes

load_dotenv()

class AlertManager:
    """
    Outbreak Detection Service.
    Scans the database for high-frequency signals and triggers alerts.
    """
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
        self.redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", "6379")), db=0)
        self.threshold = 3 # Trigger alert if 3+ cases in the window

    def check_outbreaks(self):
        try:
            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            cursor = conn.cursor()
            
            # Find entities with high frequency in the last 24 hours
            cursor.execute(
                """
                SELECT p.district_id, pe.entity_text, count(*) as signal_count
                FROM post_entities pe
                JOIN posts p ON p.id = pe.post_id
                WHERE pe.posted_at > NOW() - INTERVAL '24 hours'
                GROUP BY p.district_id, pe.entity_text
                HAVING count(*) >= %s
                """,
                (self.threshold,)
            )
            
            outbreaks = cursor.fetchall()
            for ob in outbreaks:
                self.trigger_temporal_alert(conn, ob['district_id'], ob['entity_text'], ob['signal_count'])

            self.check_temporal_spikes(conn)
            self.check_adr_disproportionality(conn)
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Alert Manager Error: {e}")

    def trigger_temporal_alert(self, conn, district_id, entity, count):
        alert_msg = {
            "type": "OUTBREAK_WARNING",
            "district_id": district_id,
            "entity": entity,
            "count": count,
            "severity": "HIGH" if count > 5 else "MEDIUM",
            "timestamp": time.time()
        }
        
        # Deduplicate alerts in Redis (don't alert for the same thing every second)
        alert_key = f"alert_sent:{district_id}:{entity}"
        if not self.redis_client.get(alert_key):
            print(f"!!! ALERT TRIGGERED: {entity} outbreak in District {district_id} !!!")
            self.redis_client.lpush("active_alerts", json.dumps(alert_msg))
            self.redis_client.ltrim("active_alerts", 0, 19)
            self.redis_client.setex(alert_key, 300, "1") # 5 minute cooldown
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO alerts (alert_type, severity, payload, confidence)
                VALUES (%s, %s, %s::jsonb, %s)
                """,
                ("TEMPORAL_SPIKE", alert_msg["severity"], json.dumps(alert_msg), 0.75 if count <= 5 else 0.9)
            )
            conn.commit()

    def check_temporal_spikes(self, conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            WITH hourly AS (
                SELECT date_trunc('hour', posted_at) AS bucket, count(*) AS count
                FROM posts
                WHERE posted_at > NOW() - INTERVAL '24 hours'
                GROUP BY 1
                ORDER BY 1
            )
            SELECT bucket::text, count FROM hourly
            """
        )
        series = [{"bucket": r["bucket"], "count": r["count"]} for r in cursor.fetchall()]
        spikes = rolling_zscore_spikes(series, min_history=6, z_threshold=2.5)
        for s in spikes[-3:]:
            payload = {"type": "TEMPORAL_SPIKE_ZSCORE", **s}
            cursor.execute(
                """
                INSERT INTO alerts (alert_type, severity, payload, confidence)
                VALUES (%s, %s, %s::jsonb, %s)
                """,
                ("TEMPORAL_SPIKE_ZSCORE", "MEDIUM", json.dumps(payload), min(0.99, 0.5 + s["z_score"] / 6.0))
            )
        conn.commit()

    def check_adr_disproportionality(self, conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT entity_text, count(*) AS c
            FROM post_entities
            WHERE posted_at > NOW() - INTERVAL '24 hours'
            GROUP BY entity_text
            """
        )
        rows = cursor.fetchall()
        if not rows:
            return

        total = sum(int(r["c"]) for r in rows)
        drugs = [r for r in rows if r["entity_text"].lower() in {"paracetamol", "coldrif", "dolo 650"}]
        events = [r for r in rows if r["entity_text"].lower() in {"fever", "cough", "vomiting", "dizziness", "stomach pain", "kidney failure"}]

        for d in drugs:
            for e in events:
                # Approximate contingency from entity frequencies for MVP disproportionality screening.
                a = min(int(d["c"]), int(e["c"]))
                b = max(0, int(d["c"]) - a)
                c = max(0, int(e["c"]) - a)
                d_other = max(0, total - (a + b + c))
                metrics = compute_prr_ror_ic(a, b, c, d_other)
                if metrics["prr"] >= 2.0 and metrics["ror"] >= 2.0:
                    payload = {
                        "type": "ADR_SIGNAL",
                        "drug": d["entity_text"],
                        "event": e["entity_text"],
                        "window": "24h",
                        "metrics": metrics
                    }
                    cursor.execute(
                        """
                        INSERT INTO alerts (alert_type, severity, payload, confidence)
                        VALUES (%s, %s, %s::jsonb, %s)
                        """,
                        ("ADR_SIGNAL", "HIGH" if metrics["prr"] >= 3 else "MEDIUM", json.dumps(payload), min(0.99, 0.6 + metrics["ic"] / 6.0))
                    )
        conn.commit()

    def run(self):
        print("Alert Manager started (Database-backed mode).")
        while True:
            self.check_outbreaks()
            time.sleep(10) # Check every 10 seconds

if __name__ == "__main__":
    manager = AlertManager()
    manager.run()
