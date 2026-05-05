import json
import os
import sys
from statistics import mean, pstdev

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.stats import compute_prr_ror_ic

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://setu_user:setu_secure_password@localhost:5432/setu_db")


def backfill_temporal(conn, hours=168, z_threshold=1.5):
    cur = conn.cursor()
    cur.execute(
        """
        WITH hourly AS (
            SELECT date_trunc('hour', posted_at) AS bucket, count(*) AS count
            FROM posts
            WHERE posted_at > NOW() - (%s || ' hours')::interval
            GROUP BY 1
            ORDER BY 1
        )
        SELECT bucket::text, count FROM hourly
        """,
        (hours,)
    )
    rows = cur.fetchall()
    if len(rows) < 4:
        return 0

    counts = [int(r["count"]) for r in rows]
    inserted = 0
    for i in range(3, len(counts)):
        hist = counts[:i]
        mu = mean(hist)
        sigma = pstdev(hist) or 1.0
        z = (counts[i] - mu) / sigma
        if z >= z_threshold:
            payload = {
                "type": "TEMPORAL_SPIKE_ZSCORE_BACKFILL",
                "bucket": rows[i]["bucket"],
                "count": counts[i],
                "baseline_mean": round(mu, 4),
                "baseline_std": round(sigma, 4),
                "z_score": round(z, 4),
                "window_hours": hours
            }
            cur.execute(
                """
                INSERT INTO alerts (alert_type, severity, payload, confidence)
                VALUES (%s, %s, %s::jsonb, %s)
                """,
                ("TEMPORAL_SPIKE_ZSCORE", "MEDIUM", json.dumps(payload), min(0.99, 0.5 + z / 5.0))
            )
            inserted += 1
    return inserted


def backfill_adr(conn, hours=168, prr_threshold=1.2, ror_threshold=1.2):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT entity_text, count(*) AS c
        FROM post_entities
        WHERE posted_at > NOW() - (%s || ' hours')::interval
        GROUP BY entity_text
        """,
        (hours,)
    )
    rows = cur.fetchall()
    if not rows:
        return 0

    total = sum(int(r["c"]) for r in rows)
    drugs = [r for r in rows if r["entity_text"].lower() in {"paracetamol", "coldrif", "dolo 650"}]
    events = [r for r in rows if r["entity_text"].lower() in {"fever", "cough", "vomiting", "dizziness", "stomach pain", "kidney failure"}]
    inserted = 0

    for d in drugs:
        for e in events:
            a = min(int(d["c"]), int(e["c"]))
            b = max(0, int(d["c"]) - a)
            c = max(0, int(e["c"]) - a)
            d_other = max(0, total - (a + b + c))
            metrics = compute_prr_ror_ic(a, b, c, d_other)
            if metrics["prr"] >= prr_threshold and metrics["ror"] >= ror_threshold:
                payload = {
                    "type": "ADR_SIGNAL_BACKFILL",
                    "drug": d["entity_text"],
                    "event": e["entity_text"],
                    "window_hours": hours,
                    "metrics": metrics
                }
                cur.execute(
                    """
                    INSERT INTO alerts (alert_type, severity, payload, confidence)
                    VALUES (%s, %s, %s::jsonb, %s)
                    """,
                    ("ADR_SIGNAL", "MEDIUM", json.dumps(payload), min(0.99, 0.6 + metrics["ic"] / 6.0))
                )
                inserted += 1
    return inserted


def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    try:
        t = backfill_temporal(conn)
        a = backfill_adr(conn)
        conn.commit()
        print(f"Backfill complete: temporal={t}, adr={a}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
