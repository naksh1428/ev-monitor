# EV Monitor

Tracks the Dutch EV charging network and exposes it over a REST API.

It pulls station data from [Open Charge Map](https://openchargemap.org), stores it in MySQL, and lets you query which stations/connectors are working or not.

## Tech stack

- **FastAPI** — REST API
- **MySQL** + **SQLAlchemy** — database
- **Alembic** — database migrations
- **Celery** + **Redis** — background jobs (data ingest, daily status snapshot)
- **Docker Compose** — runs everything together

Dependencies are managed with [uv](https://docs.astral.sh/uv/) — the package list is in `pyproject.toml`, exact pinned versions in `uv.lock`. There's no `requirements.txt`.

## Project structure

```
src/
  main.py            FastAPI app, routes registered here
  api/               route handlers (one file per resource)
    stations.py      stations: list, status, connectors, ingest from OCM
    connections.py   connectors: not-working, down-for-N-days
    operator.py      charging network operators
    reference.py     towns / status-type lookups (for filters)
  models/models.py   database tables (SQLAlchemy)
  schemas/           request/response shapes (Pydantic)
  services/          business logic (ingest, status snapshots)
  alembic/           database migrations
  celery_app.py      Celery setup + scheduled jobs
```

## Running it

1. Copy `.env` with the required values (OCM API key, DB URL, Celery/Redis URLs — see `utils/config.py` for the full list).
2. Start everything:
   ```bash
   docker compose up -d --build
   ```
   This starts MySQL, Redis, the API, a Celery worker, Celery beat (scheduler), and Flower (task monitoring UI).
3. Database migrations run automatically on API startup (`alembic upgrade head`).
4. API is at `http://localhost:8000` — visit `/docs` for interactive API docs.

## Loading data

The database starts empty. Trigger a data pull from Open Charge Map:

```bash
curl -X POST "http://localhost:8000/stations/ingest?max_results=1000"
```

This queues a background job and returns a `task_id`. Check progress with:

```bash
curl "http://localhost:8000/stations/ingest/status/<task_id>"
```

A daily job (Celery beat, 00:30 UTC) also snapshots each connector's working/not-working state for history tracking.

## API overview

| Resource | Endpoints |
|---|---|
| **Stations** | `GET /stations`, `GET /stations/locations`, `GET /stations/status`, `GET /stations/{id}/connections`, `GET /stations/{id}/status`, `GET /stations/{id}/down-connections`, `POST /stations/ingest`, `GET /stations/ingest/status/{task_id}` |
| **Connections** | `GET /connections/not-working`, `GET /connections/down` |
| **Operators** | `GET /operators`, `GET /operators/{id}` |
| **Reference** | `GET /towns`, `GET /status-types` |
| **Health** | `GET /health` |

Full request/response details are in `/docs` (Swagger UI) once the app is running.

## Database migrations

Schema changes go through Alembic, run from `src/`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```
