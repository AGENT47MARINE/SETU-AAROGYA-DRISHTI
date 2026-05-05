import os
import requests
import psycopg2
from shapely.geometry import shape
from dotenv import load_dotenv
import json

load_dotenv()

# Config
DB_URL = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
LOCAL_GEOJSON_PATH = os.getenv("DISTRICTS_GEOJSON_LOCAL_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "india_districts.geojson"))
GEOJSON_URL = os.getenv(
    "DISTRICTS_GEOJSON_URL",
    "https://raw.githubusercontent.com/geohacker/india/master/district/india_district.geojson"
)


def pick_first(props, keys, default="Unknown"):
    for key in keys:
        value = props.get(key)
        if value:
            return str(value).strip()
    return default

def seed_districts():
    data = None
    local_path = os.path.abspath(LOCAL_GEOJSON_PATH)
    if os.path.exists(local_path):
        print(f"Loading districts from local file: {local_path}")
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to read local GeoJSON: {e}")
            return
    else:
        print(f"Downloading India GeoJSON from {GEOJSON_URL} ...")
        try:
            response = requests.get(GEOJSON_URL, timeout=60)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Failed to fetch GeoJSON. Error: {e}")
            return

    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        print("Inserting into database...")
        inserted = 0
        for feature in data.get("features", []):
            props = feature["properties"]
            name = pick_first(props, ["DISTRICT", "district", "NAME_2", "dtname", "District", "district_n"])
            state = pick_first(props, ["STATE", "state", "NAME_1", "stname", "State", "state_n"])
            geom = shape(feature["geometry"])
            
            # Insert as MultiPolygon (convert to WKT)
            cursor.execute(
                """
                INSERT INTO districts (name, state, geom)
                VALUES (%s, %s, ST_Multi(ST_GeomFromText(%s, 4326)))
                ON CONFLICT DO NOTHING
                """,
                (name, state, geom.wkt)
            )
            inserted += 1
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"District data seeded successfully. Processed features: {inserted}")
    except Exception as e:
        print(f"Database connection or insertion failed: {e}")

if __name__ == "__main__":
    seed_districts()
