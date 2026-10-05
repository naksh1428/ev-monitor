import json
import os
import httpx
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import app as celery_app
from models.models import Address, Connection, Operator, Station, StatusType
from schemas.stations import (
    IngestTaskQueued,
    IngestTaskStatus,
    StationConnectionItem,
    StationDownConnectionOut,
    StationListItem,
    StationLocationOut,
    StationWorkingStatusOut,
)
from services.station_ingest import ingest_stations
from utils.config import settings
from utils.db import LocalSession, get_db

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


def _effective_connection_status(
    conn_status_type_id: int | None,
    conn_status_title: str | None,
    conn_is_operational: bool | None,
    station_status_type_id: int | None,
    station_status_title: str | None,
    station_is_operational: bool | None,
) -> tuple[int | None, str | None, bool | None]:
    """Connector status, falling back to its station's status."""
    if conn_status_type_id is not None:
        return conn_status_type_id, conn_status_title, conn_is_operational
    return station_status_type_id, station_status_title, station_is_operational


router = APIRouter(prefix="/stations", tags=["Stations"])


# --- Ingestion (write path: OCM -> DB) ----------------------------------

@celery_app.task(name="stations.ingest")
def ingest_stations_task(max_results: int = 1000, offset: int = 0) -> dict:
    """Download stations from OCM and save them."""
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
    """Start the station download in the background."""
    task = ingest_stations_task.delay(max_results, offset)
    return IngestTaskQueued(task_id=task.id, status=task.status)


@router.get("/ingest/status/{task_id}", response_model=IngestTaskStatus)
async def ingest_status(task_id: str) -> IngestTaskStatus:
    """Get the status and result of a download job."""
    result = AsyncResult(task_id, app=celery_app)
    if result.failed():
        return IngestTaskStatus(task_id=task_id, status=result.status, error=str(result.result))
    if result.successful():
        return IngestTaskStatus(task_id=task_id, status=result.status, result=result.result)
    return IngestTaskStatus(task_id=task_id, status=result.status)


# --- Read / browse (query path: DB -> API consumer) ---------------------

@router.get("", response_model=list[StationListItem])
async def list_stations(
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    operator_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationListItem]:
    """List stations with address, operator and status."""
    stmt = (
        select(
            Station.id,
            Station.uuid,
            Address.title,
            Address.town,
            Address.postcode,
            Station.operator_id,
            Operator.title.label("operator_title"),
            Station.status_type_id,
            StatusType.title.label("status_title"),
            Station.number_of_points,
        )
        .outerjoin(Address, Station.address_id == Address.id)
        .outerjoin(Operator, Station.operator_id == Operator.id)
        .outerjoin(StatusType, Station.status_type_id == StatusType.id)
    )
    if town:
        stmt = stmt.where(func.lower(Address.town).like(f"%{town.lower()}%"))
    if operator_id is not None:
        stmt = stmt.where(Station.operator_id == operator_id)
    stmt = stmt.order_by(Station.id).offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [StationListItem(**row._mapping) for row in result.all()]


@router.get("/locations", response_model=list[StationLocationOut])
async def list_station_locations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationLocationOut]:
    """List station IDs with town and postcode."""
    stmt = (
        select(Station.id, Address.town, Address.postcode)
        .outerjoin(Address, Station.address_id == Address.id)
        .order_by(Station.id)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        StationLocationOut(station_id=row.id, town=row.town, postcode=row.postcode)
        for row in result.all()
    ]


@router.get("/{station_id}/connections", response_model=list[StationConnectionItem])
async def list_station_connections(
    station_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationConnectionItem]:
    """List a station's connectors with their status."""
    station_row = (
        await db.execute(
            select(Station.id, Station.status_type_id, StatusType.title.label("status_title"), StatusType.is_operational)
            .outerjoin(StatusType, Station.status_type_id == StatusType.id)
            .where(Station.id == station_id)
        )
    ).first()
    if station_row is None:
        raise HTTPException(status_code=404, detail="Station not found")

    stmt = (
        select(
            Connection.id.label("connection_id"),
            Connection.station_id,
            Connection.connection_type_id,
            Connection.power_kw,
            Connection.amps,
            Connection.voltage,
            Connection.quantity,
            Connection.status_type_id,
            StatusType.title.label("status_title"),
            StatusType.is_operational,
        )
        .outerjoin(StatusType, Connection.status_type_id == StatusType.id)
        .where(Connection.station_id == station_id)
        .order_by(Connection.id)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)

    out = []
    for row in result.all():
        status_type_id, status_title, is_operational = _effective_connection_status(
            row.status_type_id,
            row.status_title,
            row.is_operational,
            station_row.status_type_id,
            station_row.status_title,
            station_row.is_operational,
        )
        out.append(
            StationConnectionItem(
                connection_id=row.connection_id,
                station_id=row.station_id,
                connection_type_id=row.connection_type_id,
                power_kw=row.power_kw,
                amps=row.amps,
                voltage=row.voltage,
                quantity=row.quantity,
                status_type_id=status_type_id,
                status_title=status_title,
                is_working=is_operational,
            )
        )
    return out


@router.get("/status", response_model=list[StationWorkingStatusOut])
async def list_station_status(
    is_operational: bool | None = Query(
        None, description="true = only working stations, false = only not-working stations, omit = all"
    ),
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationWorkingStatusOut]:
    """List stations by working/not-working status."""
    stmt = (
        select(
            Station.id,
            Address.title,
            Address.town,
            Address.postcode,
            Station.status_type_id,
            StatusType.title.label("status_title"),
            StatusType.is_operational,
        )
        .outerjoin(Address, Station.address_id == Address.id)
        .outerjoin(StatusType, Station.status_type_id == StatusType.id)
    )
    if is_operational is not None:
        stmt = stmt.where(StatusType.is_operational.is_(is_operational))
    if town:
        stmt = stmt.where(func.lower(Address.town).like(f"%{town.lower()}%"))
    stmt = stmt.order_by(Station.id).offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [
        StationWorkingStatusOut(
            station_id=row.id,
            title=row.title,
            town=row.town,
            postcode=row.postcode,
            status_type_id=row.status_type_id,
            status_title=row.status_title,
            is_operational=row.is_operational,
        )
        for row in result.all()
    ]


@router.get("/{station_id}/status", response_model=StationWorkingStatusOut)
async def get_station_status(station_id: int, db: AsyncSession = Depends(get_db)) -> StationWorkingStatusOut:
    """Check if a station is working right now."""
    row = (
        await db.execute(
            select(
                Station.id,
                Address.title,
                Address.town,
                Address.postcode,
                Station.status_type_id,
                StatusType.title.label("status_title"),
                StatusType.is_operational,
            )
            .outerjoin(Address, Station.address_id == Address.id)
            .outerjoin(StatusType, Station.status_type_id == StatusType.id)
            .where(Station.id == station_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Station not found")

    return StationWorkingStatusOut(
        station_id=row.id,
        title=row.title,
        town=row.town,
        postcode=row.postcode,
        status_type_id=row.status_type_id,
        status_title=row.status_title,
        is_operational=row.is_operational,
    )


@router.get("/{station_id}/down-connections", response_model=list[StationDownConnectionOut])
async def list_station_down_connections(
    station_id: int, db: AsyncSession = Depends(get_db)
) -> list[StationDownConnectionOut]:
    """List a station's connectors that aren't working."""
    station_row = (
        await db.execute(
            select(
                Station.id,
                Station.status_type_id,
                StatusType.title.label("status_title"),
                StatusType.is_operational,
                Address.town,
                Address.postcode,
            )
            .outerjoin(StatusType, Station.status_type_id == StatusType.id)
            .outerjoin(Address, Station.address_id == Address.id)
            .where(Station.id == station_id)
        )
    ).first()
    if station_row is None:
        raise HTTPException(status_code=404, detail="Station not found")

    conn_stmt = (
        select(
            Connection.id.label("connection_id"),
            Connection.status_type_id,
            StatusType.title.label("status_title"),
            StatusType.is_operational,
        )
        .outerjoin(StatusType, Connection.status_type_id == StatusType.id)
        .where(Connection.station_id == station_id)
    )
    conn_rows = (await db.execute(conn_stmt)).all()

    out = []
    for row in conn_rows:
        status_type_id, status_title, is_operational = _effective_connection_status(
            row.status_type_id,
            row.status_title,
            row.is_operational,
            station_row.status_type_id,
            station_row.status_title,
            station_row.is_operational,
        )
        if is_operational is False:
            out.append(
                StationDownConnectionOut(
                    connection_id=row.connection_id,
                    status_type_id=status_type_id,
                    status_title=status_title,
                    town=station_row.town,
                    postcode=station_row.postcode,
                )
            )
    return out


if __name__ == "__main__":
    result = fetch_stations(max_results=1000, offset=0)
    print(f"Found {len(result)} charging stations\n")
    print(type(result))
    #print(f"Keys: {result.__dict__.keys()}\n")
    #print_records(result)
    save_records(result)
