# grocr

Aggregates Czech grocery receipts from Albert, Lidl, and Penny into a single dashboard.

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy, PostgreSQL
- **Dashboard**: Grafana at `localhost:3001`
- **Infra**: Docker Compose

## Quick start

```bash
cp .env.example .env  # fill in tokens
docker compose up -d
```

API at `localhost:8000/docs` · Grafana at `localhost:3001` (admin/admin)

## Sync receipts

```bash
curl -X POST localhost:8000/sync/albert
```

## Adding a store

1. Capture traffic with mitmproxy
2. Implement `adapters/<store>.py`
3. Add sync endpoint in `api/main.py`
