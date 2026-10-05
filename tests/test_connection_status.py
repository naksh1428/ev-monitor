from datetime import date

from conftest import make_raw_station
from models.models import ConnectionStatusDaily
from services.connection_status import snapshot_connection_status
from services.station_ingest import ingest_stations


def _seed(db_session):
    ingest_stations(
        db_session,
        [
            make_raw_station(
                station_id=1,
                connections=[{"ID": 10, "StatusTypeID": 50}, {"ID": 11, "StatusTypeID": 100}],
            )
        ],
    )


def test_snapshot_records_working_flag_per_connection(db_session):
    _seed(db_session)

    count = snapshot_connection_status(db_session, snapshot_date=date(2024, 6, 1))

    assert count == 2
    rows = {row.connection_id: row for row in db_session.query(ConnectionStatusDaily).all()}
    assert rows[10].is_working is True
    assert rows[11].is_working is False
    assert rows[10].town == "Amsterdam"
    assert rows[10].operator_id == 7


def test_snapshot_same_day_overwrites_instead_of_duplicating(db_session):
    _seed(db_session)
    snapshot_connection_status(db_session, snapshot_date=date(2024, 6, 1))
    snapshot_connection_status(db_session, snapshot_date=date(2024, 6, 1))

    assert db_session.query(ConnectionStatusDaily).count() == 2
