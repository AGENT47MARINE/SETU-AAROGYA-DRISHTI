from collections import defaultdict, deque
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import redis
import time

load_dotenv()

app = FastAPI(title="Setu Aarogya API")

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
API_KEY = os.getenv("SETU_API_KEY", "")
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_URL = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")
_rate_window = defaultdict(deque)


def require_api_key(x_api_key: str | None = Header(default=None)):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def enforce_rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _rate_window[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)

def get_db():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    db_ok = False
    redis_ok = False
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db_ok = True
        conn.close()
    except Exception:
        db_ok = False

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        redis_ok = bool(r.ping())
    except Exception:
        redis_ok = False

    status = 200 if (db_ok and redis_ok) else 503
    payload = {"db": db_ok, "redis": redis_ok}
    if status != 200:
        raise HTTPException(status_code=status, detail=payload)
    return payload


@app.get("/api/signals")
def get_signals(request: Request, limit: int = 100, _=Depends(require_api_key), db = Depends(get_db)):
    enforce_rate_limit(request)
    limit = max(1, min(limit, 1000))
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT 
            p.id, 
            p.platform, 
            p.text_cleaned, 
            p.detected_lang, 
            p.posted_at,
            ST_X(p.geom) as lng,
            ST_Y(p.geom) as lat,
            d.name as district,
            (
                SELECT json_agg(e)
                FROM (
                    SELECT entity_text, entity_type, ontology_code
                    FROM post_entities
                    WHERE post_id = p.id
                ) e
            ) as entities
        FROM posts p
        LEFT JOIN districts d ON p.district_id = d.id
        ORDER BY p.posted_at DESC
        LIMIT %s
        """,
        (limit,)
    )
    return cursor.fetchall()

@app.get("/api/stats")
def get_stats(request: Request, _=Depends(require_api_key), db = Depends(get_db)):
    enforce_rate_limit(request)
    cursor = db.cursor()
    # 1. Total Signals
    cursor.execute("SELECT count(*) FROM posts")
    total_signals = cursor.fetchone()["count"]
    
    # 2. Entity Breakdown
    cursor.execute(
        """
        SELECT entity_type, count(*) as count
        FROM post_entities
        GROUP BY entity_type
        ORDER BY count DESC
        """
    )
    entities = cursor.fetchall()
    
    return {
        "total_signals": total_signals,
        "entity_breakdown": entities
    }

@app.get("/api/hotspots")
def get_hotspots(request: Request, _=Depends(require_api_key), db = Depends(get_db)):
    enforce_rate_limit(request)
    cursor = db.cursor()
    # Primary mode: DBSCAN cluster over recent geo-tagged posts.
    # Fallback mode: grid bucketing to ensure UI can render density even with sparse data.
    cursor.execute(
        """
        WITH clusters AS (
            SELECT 
                ST_ClusterDBSCAN(geom, eps => 0.01, minpoints => 2) OVER () as cluster_id,
                geom
            FROM posts
            WHERE posted_at > NOW() - INTERVAL '24 hours'
            AND geom IS NOT NULL
        ),
        clustered AS (
            SELECT 
                ST_AsGeoJSON(ST_Centroid(ST_Collect(geom)))::json as center,
                count(*) as intensity
            FROM clusters
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        ),
        fallback_grid AS (
            SELECT
                ST_AsGeoJSON(ST_Centroid(ST_Collect(geom)))::json as center,
                count(*) as intensity
            FROM (
                SELECT
                    ST_SnapToGrid(geom, 0.05, 0.05) AS cell_geom,
                    geom
                FROM posts
                WHERE posted_at > NOW() - INTERVAL '24 hours'
                AND geom IS NOT NULL
            ) g
            GROUP BY cell_geom
            HAVING count(*) >= 2
        )
        SELECT 
            center,
            intensity
        FROM clustered
        UNION ALL
        SELECT center, intensity
        FROM fallback_grid
        WHERE NOT EXISTS (SELECT 1 FROM clustered)
        ORDER BY intensity DESC
        """
    )
    return cursor.fetchall()

@app.get("/api/alerts")
def get_alerts(request: Request, _=Depends(require_api_key)):
    enforce_rate_limit(request)
    import json
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    alerts = r.lrange("active_alerts", 0, -1)
    return [json.loads(a) for a in alerts]


@app.get("/api/ingestion-status")
def get_ingestion_status(request: Request, _=Depends(require_api_key), db = Depends(get_db)):
    enforce_rate_limit(request)
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) AS c
        FROM posts
        WHERE ingested_at > NOW() - INTERVAL '5 minutes'
        """
    )
    posts_last_5m = int(cursor.fetchone()["c"])

    cursor.execute(
        """
        SELECT COALESCE(district_mapping_method, 'unknown') AS method, COUNT(*) AS c
        FROM posts
        WHERE ingested_at > NOW() - INTERVAL '24 hours'
        GROUP BY COALESCE(district_mapping_method, 'unknown')
        """
    )
    method_rows = cursor.fetchall()
    method_counts = {row["method"]: int(row["c"]) for row in method_rows}

    cursor.execute(
        """
        SELECT COUNT(*) AS c
        FROM posts
        WHERE ingested_at > NOW() - INTERVAL '24 hours'
          AND (district_id IS NULL OR geom IS NULL)
        """
    )
    unresolved_geo_24h = int(cursor.fetchone()["c"])

    dlq_total = 0
    dlq_recent = 0
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
        dlq_total = int(r.get("dlq:total") or 0)
        dlq_recent = int(r.llen("dlq:recent") or 0)
    except Exception:
        pass

    mapped_24h = (
        method_counts.get("district_mention", 0)
        + method_counts.get("state_mention", 0)
        + method_counts.get("district_fuzzy", 0)
        + method_counts.get("state_fuzzy", 0)
    )
    fallback_24h = (
        method_counts.get("default_fallback", 0)
        + method_counts.get("unresolved", 0)
        + method_counts.get("none", 0)
        + method_counts.get("unknown", 0)
    )

    return {
        "posts_last_5m": posts_last_5m,
        "posts_per_minute_estimate": round(posts_last_5m / 5.0, 2),
        "mapping_method_24h": method_counts,
        "mapped_24h": mapped_24h,
        "fallback_or_unresolved_24h": fallback_24h,
        "unresolved_geo_24h": unresolved_geo_24h,
        "dlq_total": dlq_total,
        "dlq_recent_buffer_size": dlq_recent
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
