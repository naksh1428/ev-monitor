from pydantic import BaseModel, ConfigDict


class StationListItem(BaseModel):
    id: int
    uuid: str | None
    title: str | None  # from addresses.title
    town: str | None
    postcode: str | None
    operator_id: int | None
    operator_title: str | None
    status_type_id: int | None
    status_title: str | None
    number_of_points: int | None


class StationConnectionItem(BaseModel):
    connection_id: int
    station_id: int
    connection_type_id: int | None
    power_kw: float | None
    amps: int | None
    voltage: int | None
    quantity: int | None
    status_type_id: int | None
    status_title: str | None
    is_working: bool


class NotWorkingConnectionOut(BaseModel):
    station_id: int
    connection_id: int
    operator_id: int | None
    town: str | None
    postcode: str | None
    status_type_id: int | None
    status_title: str | None


class StatusTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    is_operational: bool | None


class StationSearchConnectionItem(BaseModel):
    connection_id: int
    status_type_id: int | None
    status_title: str | None
    is_working: bool
    power_kw: float | None


class StationSearchItem(BaseModel):
    station_id: int
    title: str | None
    town: str | None
    postcode: str | None
    operator_id: int | None
    connections: list[StationSearchConnectionItem]


class StationLocationOut(BaseModel):
    station_id: int
    town: str | None
    postcode: str | None
