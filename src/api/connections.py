from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.connection_status import DownConnectionStreakOut
from services.connection_status import current_down_streak, latest_reading_per_connection
from utils.db import get_db

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/down", response_model=list[DownConnectionStreakOut])
async def get_down_connections(
    min_days: int = Query(2, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[DownConnectionStreakOut]:
    """Connections continuously not-working for more than `min_days` days, still down as of today.

    A connection's down-streak is the run of consecutive not-working daily
    snapshots ending at its latest reading; a gap in the daily snapshots or an
    intervening working reading breaks the streak.
    """
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
