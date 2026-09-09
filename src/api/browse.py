from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Address, Connection, Operator, Station, StatusType
from schemas.browse import (
    NotWorkingConnectionOut,
    StationConnectionItem,
    StationListItem,
    StationLocationOut,
    StationSearchConnectionItem,
    StationSearchItem,
    StatusTypeOut,
)
from utils.db import get_db

router = APIRouter(tags=["browse"])


@router.get("/towns", response_model=list[str])
async def list_towns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Distinct, non-empty address towns, alphabetically sorted. Paginated."""
    stmt = (
        select(Address.town)
        .where(Address.town.is_not(None), Address.town != "")
        .distinct()
        .order_by(Address.town)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


@router.get("/stations/locations", response_model=list[StationLocationOut])
async def list_station_locations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationLocationOut]:
    """Every station with its address town and postcode. Paginated."""
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


@router.get("/stations", response_model=list[StationListItem])
async def list_stations(
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    operator_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationListItem]:
    """List stations with address/operator/status joined in so each item is self-contained."""
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


@router.get("/stations/{station_id}/connections", response_model=list[StationConnectionItem])
async def list_station_connections(
    station_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationConnectionItem]:
    """All connections for one station. 404 only if the station itself doesn't exist."""
    station = await db.get(Station, station_id)
    if station is None:
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
    return [
        StationConnectionItem(
            connection_id=row.connection_id,
            station_id=row.station_id,
            connection_type_id=row.connection_type_id,
            power_kw=row.power_kw,
            amps=row.amps,
            voltage=row.voltage,
            quantity=row.quantity,
            status_type_id=row.status_type_id,
            status_title=row.status_title,
            is_working=bool(row.is_operational),
        )
        for row in result.all()
    ]


@router.get("/connections/not-working", response_model=list[NotWorkingConnectionOut])
async def list_not_working_connections(
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[NotWorkingConnectionOut]:
    """Connections whose current status_types.is_operational is exactly false.

    Statuses with is_operational left NULL (e.g. "Unknown", "Planned For Future
    Date") are excluded here, since NULL is neither true nor false in SQL - they
    are neither "working" nor "not working" by this endpoint's literal definition.
    """
    stmt = (
        select(
            Connection.station_id,
            Connection.id.label("connection_id"),
            Station.operator_id,
            Address.town,
            Address.postcode,
            Connection.status_type_id,
            StatusType.title.label("status_title"),
        )
        .join(Station, Connection.station_id == Station.id)
        .outerjoin(Address, Station.address_id == Address.id)
        .join(StatusType, Connection.status_type_id == StatusType.id)
        .where(StatusType.is_operational.is_(False))
    )
    if town:
        stmt = stmt.where(func.lower(Address.town).like(f"%{town.lower()}%"))
    stmt = stmt.order_by(Connection.id).offset(offset).limit(limit)

    result = await db.execute(stmt)
    return [NotWorkingConnectionOut(**row._mapping) for row in result.all()]


@router.get("/status-types", response_model=list[StatusTypeOut])
async def list_status_types(db: AsyncSession = Depends(get_db)) -> list[StatusTypeOut]:
    """Full status_types lookup list, for populating a status filter dropdown. Not paginated."""
    result = await db.execute(select(StatusType).order_by(StatusType.id))
    return result.scalars().all()


@router.get("/stations/search", response_model=list[StationSearchItem])
async def search_stations(
    status_type_id: int | None = Query(None, description="Filter on connection status; matches nest under their station"),
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[StationSearchItem]:
    """Stations matching the given filters, with their matching connections nested underneath.

    status_type_id is applied to the CONNECTION's status, not the station's: a
    station is included if it has at least one connection with that status, and
    only those matching connections are nested under it (not all of the
    station's connections). town filters on the station's address. With both
    filters empty this returns every station (same set as GET /stations),
    each with all of its connections nested. Pagination applies to stations;
    all matching connections for the selected page of stations are returned.
    """
    station_stmt = (
        select(Station.id, Address.title, Address.town, Address.postcode, Station.operator_id)
        .outerjoin(Address, Station.address_id == Address.id)
    )
    if town:
        station_stmt = station_stmt.where(func.lower(Address.town).like(f"%{town.lower()}%"))
    if status_type_id is not None:
        station_stmt = station_stmt.where(
            Station.id.in_(select(Connection.station_id).where(Connection.status_type_id == status_type_id))
        )
    station_stmt = station_stmt.order_by(Station.id).offset(offset).limit(limit)

    station_rows = (await db.execute(station_stmt)).all()
    if not station_rows:
        return []

    station_ids = [row.id for row in station_rows]
    conn_stmt = (
        select(
            Connection.station_id,
            Connection.id.label("connection_id"),
            Connection.status_type_id,
            StatusType.title.label("status_title"),
            StatusType.is_operational,
            Connection.power_kw,
        )
        .outerjoin(StatusType, Connection.status_type_id == StatusType.id)
        .where(Connection.station_id.in_(station_ids))
    )
    if status_type_id is not None:
        conn_stmt = conn_stmt.where(Connection.status_type_id == status_type_id)

    connections_by_station: dict[int, list[StationSearchConnectionItem]] = {}
    for row in (await db.execute(conn_stmt)).all():
        connections_by_station.setdefault(row.station_id, []).append(
            StationSearchConnectionItem(
                connection_id=row.connection_id,
                status_type_id=row.status_type_id,
                status_title=row.status_title,
                is_working=bool(row.is_operational),
                power_kw=row.power_kw,
            )
        )

    return [
        StationSearchItem(
            station_id=row.id,
            title=row.title,
            town=row.town,
            postcode=row.postcode,
            operator_id=row.operator_id,
            connections=connections_by_station.get(row.id, []),
        )
        for row in station_rows
    ]
