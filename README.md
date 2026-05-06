# Setu Aarogya Drishti

Real-time public health signal intelligence pipeline:
- Ingests Reddit health discussions
- Processes language + entities via NLP
- Maps posts to districts
- Stores events in Postgres/Timescale
- Surfaces analytics, hotspots, and alerts via API + dashboard

## Project Components

- `scripts/reddit_ingest.py`: Reddit -> Kafka producer
- `main.py`: Kafka consumer + NLP processor -> database
- `services/alerts/alert_manager.py`: alert generation worker
- `api/main.py`: FastAPI backend
- `dashboard/`: Vite + React frontend
- `scripts/init_db.py`: schema bootstrap
- `scripts/seed_districts.py`: district geometry/data bootstrap

## Prerequisites

- Python `3.10+`
- Node.js `18+` and npm
- Docker Desktop (or Docker Engine + Compose)
- Git

## Environment Setup

From repo root (`setu-aarogya-drishti`), create or update `.env`:

```env
POSTGRES_USER=setu_user
POSTGRES_PASSWORD=setu_secure_password
POSTGRES_DB=setu_db
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadminpassword
KAFKA_BROKER_URL=kafka:9092
KAFKA_BROKER=localhost:29092
DATABASE_URL=postgresql://setu_user:setu_secure_password@localhost:5432/setu_db

REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=setu-aarogya-drishti/0.1 by your_reddit_username
INDIA_SUBREDDITS=india,indiasocial,bangalore,delhi,mumbai,hyderabad,chennai,kolkata,pune,ahmedabad,kerala
MEDICAL_SUBREDDITS=indianmedschool,AskDocs,DiagnoseMe,medical_advice,medicine,pharmacy
REDDIT_KEYWORDS=fever,cough,vomit,vomiting,dizzy,dizziness,paracetamol,coldrif,dolo

DEFAULT_DISTRICT_ID=1
SETU_API_KEY=replace_with_long_random_key
CORS_ORIGINS=http://localhost:5173
RATE_LIMIT_PER_MIN=120
```

Frontend env:

1. Copy `dashboard/.env.example` to `dashboard/.env`
2. Ensure keys match backend config:

```env
VITE_API_BASE=http://localhost:8000/api
VITE_SETU_API_KEY=replace_with_same_setu_api_key
```

## Run Option 1: Local Services + Docker Infra (Recommended for Development)

### 1. Start infra containers

```bash
docker compose up -d
```

This starts Postgres/Timescale, Kafka, Zookeeper, Redis, and MinIO.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize database

```bash
python scripts/init_db.py
python scripts/seed_districts.py
```

### 4. Install dashboard dependencies

```bash
cd dashboard
npm install
cd ..
```

### 5. Start application services (use separate terminals)

Terminal A:
```bash
python main.py
```

Terminal B:
```bash
python services/alerts/alert_manager.py
```

Terminal C:
```bash
python scripts/reddit_ingest.py
```

Terminal D:
```bash
python api/main.py
```

Terminal E:
```bash
cd dashboard
npm run dev
```

### 6. Access the app

- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/healthz`
- Readiness: `http://localhost:8000/readyz`

## Run Option 2: Full Docker Stack

Run everything in containers:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Access:
- API: `http://localhost:8000`
- Dashboard: `http://localhost:5173`

Stop:

```bash
docker compose -f docker-compose.prod.yml down
```

## Quick Verification Checklist

1. `GET /healthz` returns `{"status":"ok"}`
2. `GET /readyz` returns database and redis readiness
3. `GET /api/ingestion-status` shows non-zero counters after ingestor runs
4. Dashboard loads map/cards without CORS or API key errors

If `SETU_API_KEY` is set, send header:

```http
x-api-key: <your-key>
```

## Useful Commands

Rebuild infra:

```bash
docker compose down
docker compose up -d --build
```

Tail logs:

```bash
docker compose logs -f kafka
docker compose logs -f db
```

Backfill statistical alerts (optional demo utility):

```bash
python scripts/backfill_stats_alerts.py
```

## Common Issues

- Kafka connection error:
  - Ensure `docker compose up -d` is running.
  - For host-run Python services, use `KAFKA_BROKER=localhost:29092`.

- Database connection error:
  - Confirm `DATABASE_URL` points to `localhost:5432` for host-run services.
  - Re-run `python scripts/init_db.py` after schema changes.

- Dashboard cannot fetch API:
  - Verify `VITE_API_BASE` and `VITE_SETU_API_KEY` in `dashboard/.env`.
  - Ensure backend `CORS_ORIGINS` includes `http://localhost:5173`.

- Reddit ingestion not producing data:
  - Check `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`.
  - Validate subreddit and keyword lists in `.env`.
