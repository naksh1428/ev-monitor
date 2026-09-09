from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.connection_status import DownConnectionOut
from services.connection_status import current_down_streak, latest_reading_per_connection
from utils.db import get_db

router = APIRouter(prefix="/stations", tags=["station-status"])


@router.get("/{station_id}/down-connections", response_model=list[DownConnectionOut])
async def get_down_connections(station_id: int, db: AsyncSession = Depends(get_db)) -> list[DownConnectionOut]:
    """Connections at this station whose latest daily reading is not working, and since when."""
    latest_down = await latest_reading_per_connection(db, station_id=station_id)

    out = []
    for reading in latest_down:
        down_since, _ = await current_down_streak(db, reading.connection_id, reading.snapshot_date)
        out.append(
            DownConnectionOut(
                connection_id=reading.connection_id,
                status_type_id=reading.status_type_id,
                town=reading.town,
                postcode=reading.postcode,
                down_since=down_since,
            )
        )
    return out
