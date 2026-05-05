import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
SQL_FILE = os.path.join(os.path.dirname(__file__), "init_db.sql")

def init_db():
    print(f"Connecting to database at {DB_URL}...")
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        print(f"Reading SQL from {SQL_FILE}...")
        with open(SQL_FILE, "r") as f:
            sql = f.read()
            
        print("Executing SQL commands...")
        cursor.execute(sql)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")

if __name__ == "__main__":
    init_db()
