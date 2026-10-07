import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from celery_app import app as celery_app
from models.models import Address, Connection, ConnectionStatusDaily, Station, StatusType
from utils.cache import clear_cache
from utils.db import LocalSession

logger = logging.getLogger(__name__)


def snapshot_connection_status(db: Session, snapshot_date: date | None = None) -> int:
    """Save today's status for every connector."""
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).date()

    is_operational_by_status_id = {row.id: bool(row.is_operational) for row in db.query(StatusType).all()}

    connection_rows = (
        db.query(Connection, Station.operator_id, Address.town, Address.postcode)
        .join(Station, Connection.station_id == Station.id)
        .outerjoin(Address, Station.address_id == Address.id)
        .all()
    )

    existing_by_connection_id = {
        row.connection_id: row
        for row in db.query(ConnectionStatusDaily)
        .filter(ConnectionStatusDaily.snapshot_date == snapshot_date)
        .all()
    }

    for connection, operator_id, town, postcode in connection_rows:
        is_working = is_operational_by_status_id.get(connection.status_type_id, False)
        fields = dict(
            station_id=connection.station_id,
            status_type_id=connection.status_type_id,
            is_working=is_working,
            town=town,
            postcode=postcode,
            operator_id=operator_id,
        )
        existing = existing_by_connection_id.get(connection.id)
        if existing is None:
            db.add(ConnectionStatusDaily(snapshot_date=snapshot_date, connection_id=connection.id, **fields))
        else:
            for column, value in fields.items():
                setattr(existing, column, value)

    db.commit()
    return len(connection_rows)


@celery_app.task(name="connections.snapshot_daily")
def snapshot_connection_status_task() -> int:
    """Scheduled job to record today's connector status."""
    db = LocalSession()
    try:
        count = snapshot_connection_status(db)
        clear_cache()
        logger.info("connection status snapshot written for %d connections", count)
        return count
    finally:
        db.close()


async def latest_reading_per_connection(db: AsyncSession, station_id: int | None = None):
    """Get connectors whose latest status is down."""
    latest_dates = select(
        ConnectionStatusDaily.connection_id,
        func.max(ConnectionStatusDaily.snapshot_date).label("latest_date"),
    ).group_by(ConnectionStatusDaily.connection_id)
    if station_id is not None:
        latest_dates = latest_dates.where(ConnectionStatusDaily.station_id == station_id)
    latest_dates = latest_dates.subquery()

    stmt = select(ConnectionStatusDaily).join(
        latest_dates,
        and_(
            ConnectionStatusDaily.connection_id == latest_dates.c.connection_id,
            ConnectionStatusDaily.snapshot_date == latest_dates.c.latest_date,
        ),
    ).where(ConnectionStatusDaily.is_working.is_(False))

    result = await db.execute(stmt)
    return result.scalars().all()


async def current_down_streak(db: AsyncSession, connection_id: int, latest_date: date) -> tuple[date, int]:
    """Find when a connector's current down streak started."""
    stmt = (
        select(ConnectionStatusDaily.snapshot_date, ConnectionStatusDaily.is_working)
        .where(
            ConnectionStatusDaily.connection_id == connection_id,
            ConnectionStatusDaily.snapshot_date <= latest_date,
        )
        .order_by(ConnectionStatusDaily.snapshot_date.desc())
    )
    result = await db.execute(stmt)

    down_since = latest_date
    expected = latest_date
    for snapshot_date, is_working in result.all():
        if snapshot_date != expected or is_working:
            break
        down_since = snapshot_date
        expected = snapshot_date - timedelta(days=1)

    days_down = (latest_date - down_since).days + 1
    return down_since, days_down
