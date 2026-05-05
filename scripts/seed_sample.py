import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")

def seed_sample():
    print("Seeding sample district (Bhopal)...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Simple point/box for Bhopal for testing
        # MultiPolygon: (((77.3 23.2, 77.5 23.2, 77.5 23.4, 77.3 23.4, 77.3 23.2)))
        cursor.execute(
            """
            INSERT INTO districts (name, state, geom)
            VALUES (%s, %s, ST_Multi(ST_GeomFromText(%s, 4326)))
            ON CONFLICT DO NOTHING
            """,
            ("Bhopal", "Madhya Pradesh", "POLYGON((77.3 23.2, 77.5 23.2, 77.5 23.4, 77.3 23.4, 77.3 23.2))")
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Sample district seeded.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    seed_sample()
