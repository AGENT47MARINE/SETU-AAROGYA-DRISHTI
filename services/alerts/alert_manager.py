import os
import time
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv

load_dotenv()

class AlertManager:
    """
    Outbreak Detection Service.
    Scans the database for high-frequency signals and triggers alerts.
    """
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
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
                self.trigger_alert(ob['district_id'], ob['entity_text'], ob['signal_count'])
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Alert Manager Error: {e}")

    def trigger_alert(self, district_id, entity, count):
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

    def run(self):
        print("Alert Manager started (Database-backed mode).")
        while True:
            self.check_outbreaks()
            time.sleep(10) # Check every 10 seconds

if __name__ == "__main__":
    manager = AlertManager()
    manager.run()
