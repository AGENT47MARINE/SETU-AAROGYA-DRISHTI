# Setu Aarogya Drishti: Developer Build Notes

## Phase 0: Infrastructure Setup

1. **Start Docker Desktop**: Ensure the Docker engine is running.
2. **Spin up Backbone**:
   ```bash
   docker compose up -d
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Initialize Database**:
   ```bash
   python scripts/init_db.py
   ```
5. **Seed Districts**:
   ```bash
   python scripts/seed_districts.py
   ```

## Phase 1: NLP Core Implementation

Next steps:
- Implement `services/nlp/language_detector.py`
- Implement `services/nlp/normalizer.py`
- Implement `services/nlp/translator.py`
- Fine-tune NER model using `services/nlp/ner/training/train_ner.py`

## Real-time MVP Runbook (Practical)

1. Start infra:
   ```bash
   docker compose up -d
   ```
2. Init schema + districts:
   ```bash
   python scripts/init_db.py
   python scripts/seed_districts.py
   ```
   Notes:
   - `seed_districts.py` reads `DISTRICTS_GEOJSON_URL` (defaults to an India district GeoJSON).
   - Local-first loading is enabled via `DISTRICTS_GEOJSON_LOCAL_PATH` (default: `data/india_districts.geojson`).
   - Re-run `init_db.py` once after pulling latest changes to apply the district uniqueness index.
3. Start NLP processor (Kafka -> NLP -> Postgres):
   ```bash
   python main.py
   ```
4. Start alerts worker:
   ```bash
   python services/alerts/alert_manager.py
   ```
5. Start Reddit real-time ingestion (requires Reddit API keys in `.env`):
   ```bash
   python scripts/reddit_ingest.py
   ```
   - The ingestor now maps district/state mentions from post text to `district_id`.
   - Source selection is split by `INDIA_SUBREDDITS` and `MEDICAL_SUBREDDITS` (merged automatically).
6. Start API:
   ```bash
   python api/main.py
   ```
7. Start dashboard:
   ```bash
   cd dashboard
   npm run dev
   ```
   - Set `dashboard/.env` from `dashboard/.env.example` and use the same `SETU_API_KEY`.

## Production Beta Notes

- API now supports:
  - API key auth via `x-api-key` header (`SETU_API_KEY`)
  - CORS allow-list (`CORS_ORIGINS`)
  - Basic in-memory rate limit (`RATE_LIMIT_PER_MIN`)
  - `/healthz` and `/readyz` endpoints for liveness/readiness checks
  - `/api/ingestion-status` for throughput + geo-mapping + DLQ telemetry
  - `/api/triage/queue` and `/api/triage/{id}/decision` for human review workflow
  - `/api/geo-review/queue` for unresolved location review
  - `/api/stats/advanced` for ADR and temporal statistical provenance
- NLP processor now sends failed records to DLQ topic `raw_posts_dlq`.
- Posts are deduplicated by `(platform, post_id_hash)` at DB level.
- Geo mapping supports alias + fuzzy matching via:
  - `services/geospatial/location_aliases.json`
  - `DISTRICT_FUZZY_THRESHOLD` env (default `92`)

## Statistical Engine (Phase B)

- `services/alerts/alert_manager.py` now generates:
  - `TEMPORAL_SPIKE` alerts from count thresholds
  - `TEMPORAL_SPIKE_ZSCORE` alerts from rolling z-score spikes
  - `ADR_SIGNAL` alerts from PRR/ROR/IC disproportionality screening
- Statistical helpers:
  - `services/stats/adr_metrics.py`
  - `services/stats/temporal.py`
- Demo backfill utility:
  - `python scripts/backfill_stats_alerts.py`
  - Inserts historical ADR/temporal statistical alerts for showcase datasets.

### Launch shared stack (beta)
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
