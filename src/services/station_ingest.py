import logging
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy.orm import Session

from models.models import Address, Connection, Operator, Station, StatusSnapshot, StatusType
from schemas.stations import AddressInfoIn, IngestSummary, StationIn

logger = logging.getLogger(__name__)

# OCM StatusType codes, per the task spec. title/is_operational are seeded once per ingest run.
KNOWN_STATUS_TYPES: dict[int, tuple[str, bool | None]] = {
    0: ("Unknown", None),
    10: ("Available", True),
    20: ("Currently In Use", True),
    30: ("Temporarily Unavailable", False),
    50: ("Operational", True),
    75: ("Partly Operational", True),
    100: ("Not Operational", False),
    150: ("Planned For Future Date", None),
    200: ("Removed", False),
}


def _to_naive_utc(value: datetime | None) -> datetime | None:
    """MySQL DATETIME columns here are naive; normalize any tz-aware value to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None)


def seed_status_types(db: Session) -> None:
    """Upsert the static OCM status-type lookup rows."""
    for status_id, (title, is_operational) in KNOWN_STATUS_TYPES.items():
        status_type = db.get(StatusType, status_id)
        if status_type is None:
            db.add(StatusType(id=status_id, title=title, is_operational=is_operational))
        else:
            status_type.title = title
            status_type.is_operational = is_operational
    db.commit()


def _ensure_status_type(db: Session, status_type_id: int | None) -> None:
    """Insert a placeholder row for a status code outside KNOWN_STATUS_TYPES so the FK never breaks."""
    if status_type_id is None or status_type_id in KNOWN_STATUS_TYPES:
        return
    if db.get(StatusType, status_type_id) is None:
        db.add(StatusType(id=status_type_id, title=f"Unknown ({status_type_id})", is_operational=None))


def _upsert_operator(db: Session, operator_id: int | None) -> None:
    """Ensure the operator row exists. OCM's compact=true payload carries no operator title/website."""
    if operator_id is None:
        return
    if db.get(Operator, operator_id) is None:
        db.add(Operator(id=operator_id))


def _upsert_address(db: Session, address: AddressInfoIn) -> None:
    fields = dict(
        title=address.title,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        town=address.town,
        state_or_province=address.state_or_province,
        postcode=address.postcode,
        country_id=address.country_id,
        latitude=address.latitude,
        longitude=address.longitude,
    )
    existing = db.get(Address, address.id)
    if existing is None:
        db.add(Address(id=address.id, **fields))
    else:
        for column, value in fields.items():
            setattr(existing, column, value)


def _upsert_station(db: Session, station: StationIn) -> bool:
    """Upsert the station row. Returns True if this was a fresh insert (vs an update)."""
    fields = dict(
        uuid=station.uuid,
        operator_id=station.operator_id,
        usage_type_id=station.usage_type_id,
        address_id=station.address.id,
        number_of_points=station.number_of_points,
        status_type_id=station.status_type_id,
        date_created=_to_naive_utc(station.date_created),
        date_last_status_update=_to_naive_utc(station.date_last_status_update),
    )
    existing = db.get(Station, station.id)
    if existing is None:
        db.add(Station(id=station.id, **fields))
        return True
    for column, value in fields.items():
        setattr(existing, column, value)
    return False


def _upsert_connections(db: Session, station_id: int, connections: list) -> int:
    for conn in connections:
        _ensure_status_type(db, conn.status_type_id)
        fields = dict(
            station_id=station_id,
            connection_type_id=conn.connection_type_id,
            current_type_id=conn.current_type_id,
            level_id=conn.level_id,
            power_kw=conn.power_kw,
            amps=conn.amps,
            voltage=conn.voltage,
            quantity=conn.quantity,
            status_type_id=conn.status_type_id,
        )
        existing = db.get(Connection, conn.id)
        if existing is None:
            db.add(Connection(id=conn.id, **fields))
        else:
            for column, value in fields.items():
                setattr(existing, column, value)
    return len(connections)


def _add_status_snapshot(db: Session, station: StationIn) -> None:
    """Append-only history row; never updated."""
    db.add(
        StatusSnapshot(
            station_id=station.id,
            status_type_id=station.status_type_id,
            source_updated_at=_to_naive_utc(station.date_last_status_update),
            checked_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )


def ingest_stations(db: Session, raw_records: list[dict]) -> IngestSummary:
    """Validate and persist a batch of raw OCM station records.

    Each station's writes (address, operator, station, connections, snapshot)
    commit or roll back together. A record that fails validation or a DB write
    is skipped and logged; it does not abort the rest of the batch.
    """
    seed_status_types(db)

    processed = inserted = updated = connections_written = snapshots_added = skipped = 0
    errors: list[str] = []

    for raw in raw_records:
        raw_id = raw.get("ID", "<unknown>")
        try:
            station = StationIn.model_validate(raw)
        except ValidationError as exc:
            skipped += 1
            msg = f"station {raw_id}: validation failed - {exc.errors()[0]['msg']}"
            errors.append(msg)
            logger.warning(msg)
            continue

        try:
            _ensure_status_type(db, station.status_type_id)
            _upsert_operator(db, station.operator_id)
            _upsert_address(db, station.address)
            is_new = _upsert_station(db, station)
            connections_written += _upsert_connections(db, station.id, station.connections)
            _add_status_snapshot(db, station)
            db.commit()
        except Exception as exc:  # a single bad station must not abort the batch
            db.rollback()
            skipped += 1
            msg = f"station {station.id}: write failed - {exc}"
            errors.append(msg)
            logger.exception(msg)
            continue

        processed += 1
        snapshots_added += 1
        if is_new:
            inserted += 1
        else:
            updated += 1

    return IngestSummary(
        fetched=len(raw_records),
        processed=processed,
        stations_inserted=inserted,
        stations_updated=updated,
        connections_written=connections_written,
        snapshots_added=snapshots_added,
        skipped=skipped,
        errors=errors,
    )
