from datetime import datetime, timedelta, timezone

from conftest import make_raw_station
from models.models import Connection, Operator, Station, StatusSnapshot, StatusType
from services.station_ingest import KNOWN_STATUS_TYPES, _to_naive_utc, ingest_stations, seed_status_types


def test_to_naive_utc_converts_aware_datetime():
    aware = datetime(2024, 6, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))

    assert _to_naive_utc(aware) == datetime(2024, 6, 1, 10, 0)


def test_to_naive_utc_keeps_naive_and_none():
    naive = datetime(2024, 6, 1, 12, 0)

    assert _to_naive_utc(naive) == naive
    assert _to_naive_utc(None) is None


def test_seed_status_types_is_idempotent(db_session):
    seed_status_types(db_session)
    seed_status_types(db_session)

    assert db_session.query(StatusType).count() == len(KNOWN_STATUS_TYPES)
    assert db_session.get(StatusType, 100).is_operational is False


def test_ingest_inserts_new_station(db_session):
    summary = ingest_stations(db_session, [make_raw_station(station_id=1)])

    assert summary.fetched == 1
    assert summary.stations_inserted == 1
    assert summary.stations_updated == 0
    assert summary.connections_written == 1
    assert summary.skipped == 0
    assert db_session.get(Station, 1).date_last_status_update == datetime(2024, 6, 1, 10, 0)
    assert db_session.get(Operator, 7) is not None
    assert db_session.query(StatusSnapshot).count() == 1


def test_ingest_updates_existing_station(db_session):
    ingest_stations(db_session, [make_raw_station(station_id=1, status_type_id=50)])
    summary = ingest_stations(db_session, [make_raw_station(station_id=1, status_type_id=100)])

    assert summary.stations_inserted == 0
    assert summary.stations_updated == 1
    assert db_session.get(Station, 1).status_type_id == 100
    assert db_session.query(StatusSnapshot).count() == 2


def test_ingest_skips_invalid_record_and_continues(db_session):
    summary = ingest_stations(db_session, [{"ID": 99}, make_raw_station(station_id=2)])

    assert summary.processed == 1
    assert summary.skipped == 1
    assert summary.errors[0].startswith("station 99: validation failed")
    assert db_session.get(Station, 2) is not None


def test_ingest_adds_placeholder_for_unknown_status_code(db_session):
    raw = make_raw_station(station_id=3, connections=[{"ID": 30, "StatusTypeID": 999}])

    ingest_stations(db_session, [raw])

    assert db_session.get(StatusType, 999).title == "Unknown (999)"
    assert db_session.get(Connection, 30).status_type_id == 999
