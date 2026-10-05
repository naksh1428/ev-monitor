from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AddressInfoIn(BaseModel):
    model_config = {"populate_by_name": True}

    id: int = Field(alias="ID")
    title: Optional[str] = Field(default=None, alias="Title")
    address_line1: Optional[str] = Field(default=None, alias="AddressLine1")
    address_line2: Optional[str] = Field(default=None, alias="AddressLine2")
    town: Optional[str] = Field(default=None, alias="Town")
    state_or_province: Optional[str] = Field(default=None, alias="StateOrProvince")
    postcode: Optional[str] = Field(default=None, alias="Postcode")
    country_id: Optional[int] = Field(default=None, alias="CountryID")
    latitude: Optional[float] = Field(default=None, alias="Latitude")
    longitude: Optional[float] = Field(default=None, alias="Longitude")


class ConnectionIn(BaseModel):
    model_config = {"populate_by_name": True}

    id: int = Field(alias="ID")
    connection_type_id: Optional[int] = Field(default=None, alias="ConnectionTypeID")
    current_type_id: Optional[int] = Field(default=None, alias="CurrentTypeID")
    level_id: Optional[int] = Field(default=None, alias="LevelID")
    power_kw: Optional[float] = Field(default=None, alias="PowerKW")
    amps: Optional[int] = Field(default=None, alias="Amps")
    voltage: Optional[int] = Field(default=None, alias="Voltage")
    quantity: Optional[int] = Field(default=None, alias="Quantity")
    status_type_id: Optional[int] = Field(default=None, alias="StatusTypeID")


class StationIn(BaseModel):
    model_config = {"populate_by_name": True}

    id: int = Field(alias="ID")
    uuid: Optional[str] = Field(default=None, alias="UUID")
    operator_id: Optional[int] = Field(default=None, alias="OperatorID")
    usage_type_id: Optional[int] = Field(default=None, alias="UsageTypeID")
    address: AddressInfoIn = Field(alias="AddressInfo")
    number_of_points: Optional[int] = Field(default=None, alias="NumberOfPoints")
    status_type_id: Optional[int] = Field(default=None, alias="StatusTypeID")
    date_created: Optional[datetime] = Field(default=None, alias="DateCreated")
    date_last_status_update: Optional[datetime] = Field(default=None, alias="DateLastStatusUpdate")
    connections: list[ConnectionIn] = Field(default_factory=list, alias="Connections")

    @field_validator("connections", mode="before")
    @classmethod
    def _empty_when_null(cls, v):
        return v or []


class IngestSummary(BaseModel):
    fetched: int
    processed: int
    stations_inserted: int
    stations_updated: int
    connections_written: int
    snapshots_added: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class IngestTaskQueued(BaseModel):
    task_id: str
    status: str


class IngestTaskStatus(BaseModel):
    task_id: str
    status: str
    result: Optional[IngestSummary] = None
    error: Optional[str] = None


# --- Read/browse schemas -----------------------------------------------

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


class StationLocationOut(BaseModel):
    station_id: int
    town: str | None
    postcode: str | None


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
    is_working: bool | None  # None = genuinely unclear (e.g. "Unknown"/"Planned For Future Date")


class StationDownConnectionOut(BaseModel):
    connection_id: int
    status_type_id: int | None
    status_title: str | None
    town: str | None
    postcode: str | None


class StationWorkingStatusOut(BaseModel):
    station_id: int
    title: str | None
    town: str | None
    postcode: str | None
    status_type_id: int | None
    status_title: str | None  # e.g. "Operational", "Not Operational", "Unknown"
    is_operational: bool | None  # None = unclear (e.g. "Unknown"/"Planned For Future Date")
