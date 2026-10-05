import pytest
from pydantic import ValidationError

from conftest import make_raw_station
from schemas.stations import StationIn


def test_station_in_parses_ocm_aliases():
    station = StationIn.model_validate(make_raw_station(station_id=5))

    assert station.id == 5
    assert station.operator_id == 7
    assert station.address.id == 500
    assert station.address.town == "Amsterdam"
    assert len(station.connections) == 1
    assert station.connections[0].power_kw == 22.0


def test_station_in_null_connections_become_empty_list():
    raw = make_raw_station()
    raw["Connections"] = None

    assert StationIn.model_validate(raw).connections == []


def test_station_in_requires_address():
    raw = make_raw_station()
    del raw["AddressInfo"]

    with pytest.raises(ValidationError):
        StationIn.model_validate(raw)
