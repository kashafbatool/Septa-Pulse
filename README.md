# SEPTA Pulse — Real-Time Transit Analytics

> Automated data pipeline and spatial analytics dashboard for the Philadelphia transit network.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SEPTA Open Data API                      │
│  TransitViewAll (buses)  TrainView (rail)  Alerts               │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (every 30s)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Pipeline (Python)                         │
│  fetcher.py → cleaner.py → loader.py                            │
│                                                                   │
│  Local: APScheduler (docker-compose pipeline service)            │
│  AWS:   Lambda + EventBridge rule (rate(1 minute))               │
└───────────────────────────────┬─────────────────────────────────┘
                                │ SQLAlchemy bulk insert
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL 15 + PostGIS                              │
│  vehicle_positions  │  alerts  │  route_stats                    │
│  Local: Docker      │  AWS: RDS db.t3.micro                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI REST API                               │
│  /api/vehicles/live    /api/analytics/delays                     │
│  /api/vehicles/history /api/analytics/heatmap                    │
│  /api/analytics/summary /api/analytics/route-efficiency          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ JSON
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               Browser Dashboard (Leaflet.js + Chart.js)          │
│  • Live vehicle map (Philadelphia, dark tile layer)              │
│  • Historical heatmap (density by location)                      │
│  • Delay rankings bar chart                                       │
│  • On-time performance doughnut chart                            │
│  • Auto-refresh every 30 seconds                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quickstart (Local with Docker)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/septa-pulse.git
cd septa-pulse
cp .env.example .env
```

### 2. Start all services

```bash
docker-compose up --build
```

This starts:
| Service | Description | Port |
|---------|-------------|------|
| `db` | PostgreSQL 15 + PostGIS | 5432 |
| `migrate` | Runs Alembic migrations once | — |
| `api` | FastAPI backend | **8000** |
| `pipeline` | SEPTA data fetcher (30s interval) | — |

### 3. Open the dashboard

```
http://localhost:8000
```

Wait ~60 seconds for the first pipeline cycle to populate data, then vehicles will appear on the map.

### 4. Explore the API

```bash
# Live vehicles
curl http://localhost:8000/api/vehicles/live | python3 -m json.tool

# Filter by route
curl "http://localhost:8000/api/vehicles/live?route=33"

# Delay rankings
curl http://localhost:8000/api/analytics/delays

# System summary
curl http://localhost:8000/api/analytics/summary
```

Interactive docs: http://localhost:8000/docs

---

## Project Structure

```
septa-pulse/
├── src/
│   ├── pipeline/
│   │   ├── fetcher.py          # SEPTA API client (TransitViewAll, TrainView, Alerts)
│   │   ├── cleaner.py          # Data normalization, delay parsing
│   │   └── loader.py           # Bulk PostgreSQL insert
│   ├── database/
│   │   ├── models.py           # SQLAlchemy + PostGIS models
│   │   ├── connection.py       # Engine / session factory
│   │   └── migrations/         # Alembic scripts
│   ├── api/
│   │   ├── main.py             # FastAPI app
│   │   └── routes/
│   │       ├── vehicles.py     # /api/vehicles/*
│   │       └── analytics.py    # /api/analytics/*
│   └── scheduler/
│       └── lambda_handler.py   # Lambda entry point + local APScheduler
├── dashboard/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js              # API fetch helpers
│       ├── map.js              # Leaflet map + heatmap
│       ├── charts.js           # Chart.js visualizations
│       └── app.js              # Main controller
├── infrastructure/terraform/   # AWS Lambda + RDS + VPC + EventBridge
├── tests/                      # pytest: fetcher, cleaner, API
├── .github/workflows/
│   ├── ci.yml                  # Lint + test on every push/PR
│   └── deploy.yml              # Deploy Lambda on merge to main
├── docker-compose.yml
├── Dockerfile
└── alembic.ini
```

---

## API Reference

### Vehicles

| Method | Endpoint | Params | Description |
|--------|----------|--------|-------------|
| GET | `/api/vehicles/live` | `mode`, `route` | Current positions (last 90s) |
| GET | `/api/vehicles/history` | `route` *(required)*, `hours` | Historical trail |
| GET | `/api/vehicles/routes` | `mode` | All routes seen in last 24h |

### Analytics

| Method | Endpoint | Params | Description |
|--------|----------|--------|-------------|
| GET | `/api/analytics/delays` | `hours`, `mode`, `limit` | Avg delay per route (worst-first) |
| GET | `/api/analytics/heatmap` | `hours`, `mode` | GeoJSON density data |
| GET | `/api/analytics/route-efficiency` | `hours` | On-time % per route |
| GET | `/api/analytics/summary` | — | Live count, delayed count, 24h positions |

---

## Database Schema

### `vehicle_positions`
| Column | Type | Description |
|--------|------|-------------|
| `vehicle_id` | TEXT | SEPTA vehicle or train number |
| `route` | TEXT | Route identifier |
| `mode` | TEXT | `bus` / `trolley` / `rail` |
| `lat`, `lon` | FLOAT | WGS84 coordinates |
| `geom` | GEOMETRY(Point,4326) | PostGIS spatial column (GiST indexed) |
| `offset_sec` | INT | Delay in seconds (positive = late) |
| `fetched_at` | TIMESTAMPTZ | Pipeline capture time |

### `alerts`
Service alerts keyed by route with message text.

### `route_stats`
Aggregated per-route snapshots: avg delay, vehicle count, on-time %.

---

## Running Tests

```bash
pip install -r requirements-dev.txt

# Unit tests only (no DB required)
pytest tests/test_fetcher.py tests/test_cleaner.py -v

# Full suite (requires PostgreSQL)
DATABASE_URL=postgresql://septa:septa@localhost:5432/septapulse_test pytest tests/ -v
```

---

## AWS Deployment

### Prerequisites
- AWS CLI configured (`aws configure`)
- Terraform >= 1.6
- An existing S3 bucket for Lambda artifacts

### 1. Provision infrastructure

```bash
cd infrastructure/terraform

terraform init
terraform plan -var="db_password=YourSecurePassword" -var="s3_lambda_bucket=your-bucket"
terraform apply
```

### 2. Set GitHub Secrets

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | IAM user key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `AWS_REGION` | e.g. `us-east-1` |
| `S3_LAMBDA_BUCKET` | Your S3 bucket name |

### 3. Deploy

Push to `main` — the `deploy.yml` workflow will:
1. Package the pipeline into a Lambda zip
2. Upload to S3
3. Update the Lambda function code
4. Run Alembic migrations against RDS
5. Invoke Lambda once to verify

---

## SEPTA API Endpoints Used

| Endpoint | Data |
|----------|------|
| `TransitViewAll/index.php` | All bus & trolley positions |
| `TrainView/index.php` | Regional rail train positions |
| `Alerts/index.php?req1=all` | Active service alerts |

Data sourced from [SEPTA Open Data](https://www3.septa.org/) — no API key required.

---

## CI/CD Pipeline

```
Push / PR → ci.yml
  ├── black (formatting check)
  ├── flake8 (linting)
  └── pytest (unit + integration tests with PostGIS)

Merge to main → deploy.yml
  ├── Build Lambda zip (src/ + pip dependencies)
  ├── Upload to S3
  ├── Update Lambda function code
  ├── Run Alembic migrations against RDS
  └── Smoke test (invoke Lambda, verify output)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data Pipeline | Python 3.11, `requests`, `APScheduler` |
| Database | PostgreSQL 15, PostGIS, SQLAlchemy, Alembic |
| API | FastAPI, Uvicorn, Mangum (Lambda adapter) |
| Dashboard | Leaflet.js, Leaflet.heat, Chart.js |
| Infrastructure | AWS Lambda, RDS, EventBridge, VPC, Terraform |
| CI/CD | GitHub Actions |
| Local Dev | Docker Compose, `postgis/postgis:15-3.3` |
