from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from conftest import make_raw_station
from services.connection_status import snapshot_connection_status
from services.station_ingest import ingest_stations


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects_to_docs(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/docs"


def test_list_stations_filters_by_town(client, db_session):
    ingest_stations(
        db_session,
        [make_raw_station(station_id=1, town="Amsterdam"), make_raw_station(station_id=2, town="Utrecht")],
    )

    response = client.get("/stations", params={"town": "amster"})

    assert response.status_code == 200
    body = response.json()
    assert [s["id"] for s in body] == [1]
    assert body[0]["status_title"] == "Operational"


def test_station_status_not_found(client):
    response = client.get("/stations/12345/status")

    assert response.status_code == 404


def test_station_connections_fall_back_to_station_status(client, db_session):
    raw = make_raw_station(station_id=1, status_type_id=100, connections=[{"ID": 10, "StatusTypeID": None}])
    ingest_stations(db_session, [raw])

    response = client.get("/stations/1/connections")

    assert response.status_code == 200
    connection = response.json()[0]
    assert connection["status_type_id"] == 100
    assert connection["is_working"] is False


def test_station_down_connections(client, db_session):
    raw = make_raw_station(
        station_id=1, connections=[{"ID": 10, "StatusTypeID": 50}, {"ID": 11, "StatusTypeID": 30}]
    )
    ingest_stations(db_session, [raw])

    response = client.get("/stations/1/down-connections")

    assert response.status_code == 200
    assert [c["connection_id"] for c in response.json()] == [11]


def test_status_types_listed_after_seed(client, db_session):
    ingest_stations(db_session, [])

    response = client.get("/status-types")

    assert response.status_code == 200
    assert response.json()[0] == {"id": 0, "title": "Unknown", "is_operational": None}


def test_operator_not_found(client):
    assert client.get("/operators/1").status_code == 404


def test_connections_down_counts_consecutive_days(client, db_session):
    raw = make_raw_station(station_id=1, connections=[{"ID": 10, "StatusTypeID": 100}])
    ingest_stations(db_session, [raw])
    today = date(2024, 6, 10)
    for days_ago in range(3):
        snapshot_connection_status(db_session, snapshot_date=today - timedelta(days=days_ago))

    response = client.get("/connections/down", params={"min_days": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["connection_id"] == 10
    assert body[0]["days_down"] == 3
    assert body[0]["down_since"] == "2024-06-08"


def test_ingest_queues_celery_task(client):
    fake_task = MagicMock(id="abc-123", status="PENDING")
    with patch("api.stations.ingest_stations_task.delay", return_value=fake_task) as delay:
        response = client.post("/stations/ingest", params={"max_results": 10})

    assert response.status_code == 202
    assert response.json() == {"task_id": "abc-123", "status": "PENDING"}
    delay.assert_called_once_with(10, 0)
