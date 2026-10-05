from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Address, Connection, Station, StatusType
from schemas.connections import DownConnectionStreakOut, NotWorkingConnectionOut
from services.connection_status import current_down_streak, latest_reading_per_connection
from utils.db import get_db

router = APIRouter(prefix="/connections", tags=["Connections"])


@router.get("/not-working", response_model=list[NotWorkingConnectionOut])
async def list_not_working_connections(
    town: str | None = Query(None, description="Case-insensitive partial match on address town"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[NotWorkingConnectionOut]:
    """List connectors that are clearly broken right now."""
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


@router.get("/down", response_model=list[DownConnectionStreakOut])
async def list_down_connections(
    min_days: int = Query(2, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[DownConnectionStreakOut]:
    """List connectors down for more than `min_days` days in a row."""
    latest_down = await latest_reading_per_connection(db)

    out = []
    for reading in latest_down:
        down_since, days_down = await current_down_streak(db, reading.connection_id, reading.snapshot_date)
        if days_down > min_days:
            out.append(
                DownConnectionStreakOut(
                    station_id=reading.station_id,
                    connection_id=reading.connection_id,
                    operator_id=reading.operator_id,
                    town=reading.town,
                    postcode=reading.postcode,
                    down_since=down_since,
                    days_down=days_down,
                )
            )
    return out
