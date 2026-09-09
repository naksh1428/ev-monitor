import json
import os
import httpx
from celery.result import AsyncResult
from fastapi import APIRouter, Query

from celery_app import app as celery_app
from schemas.stations import IngestTaskQueued, IngestTaskStatus
from services.station_ingest import ingest_stations
from utils.config import settings
from utils.db import LocalSession

#BASE = "https://api.openchargemap.io/v3/poi"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch_stations(max_results: int = 5, offset: int = 0) -> list[dict]:
    resp = httpx.get(
        settings.BASE,
        params={
            "key": settings.OCM_API_KEY,
            "countrycode": settings.COUNTRY_CODE,   #settings.country_code,
            "maxresults": max_results,
            "compact": True,
            "opendata": True,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    with open ("../api_result.txt", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(resp.json())
    return resp.json()

def print_stations(stations: list[dict]) -> None:
    print(f"Found {len(stations)} charging stations\n")
    print("KEY: ", settings.OCM_API_KEY,"\n\n")
    for s in stations:
        addr = s.get("AddressInfo", {})
        name = addr.get("Title", "Unknown")
        town = addr.get("Town", "?")
        connections = s.get("Connections", []) or []
        statuses = [(c.get("StatusType") or {}).get("Title", "Unknown") for c in connections]
        powers = [c.get("PowerKW") for c in connections if c.get("PowerKW")]
        power_str = f"{max(powers):.0f} kW" if powers else "n/a"
        print(f"- {name} ({town}) | {len(connections)} connectors, max {power_str} | status: {', '.join(statuses) or 'unknown'}")


def save_records(stations: list[dict], path: str | None = None) -> None:
    if path is None:
        path = os.path.join(PROJECT_ROOT, "result-set", "../stations.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in stations:
            f.write(json.dumps(record, indent=2))
            f.write("\n")


router = APIRouter(prefix="/stations", tags=["stations"])


@celery_app.task(name="stations.ingest")
def ingest_stations_task(max_results: int = 1000, offset: int = 0) -> dict:
    """Celery task: fetch stations from OCM and upsert them into the database."""
    db = LocalSession()
    try:
        raw_records = fetch_stations(max_results=max_results, offset=offset)
        return ingest_stations(db, raw_records).model_dump()
    finally:
        db.close()


@router.post("/ingest", response_model=IngestTaskQueued, status_code=202)
async def ingest(
    max_results: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
) -> IngestTaskQueued:
    """Queue an OCM fetch + DB ingest as a background Celery task."""
    task = ingest_stations_task.delay(max_results, offset)
    return IngestTaskQueued(task_id=task.id, status=task.status)


@router.get("/ingest/status/{task_id}", response_model=IngestTaskStatus)
async def ingest_status(task_id: str) -> IngestTaskStatus:
    """Check the status/result of a previously queued ingest task."""
    result = AsyncResult(task_id, app=celery_app)
    if result.failed():
        return IngestTaskStatus(task_id=task_id, status=result.status, error=str(result.result))
    if result.successful():
        return IngestTaskStatus(task_id=task_id, status=result.status, result=result.result)
    return IngestTaskStatus(task_id=task_id, status=result.status)


if __name__ == "__main__":
    result = fetch_stations(max_results=1000, offset=0)
    print(f"Found {len(result)} charging stations\n")
    print(type(result))
    #print(f"Keys: {result.__dict__.keys()}\n")
    #print_records(result)
    save_records(result)
