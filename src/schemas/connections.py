from datetime import date

from pydantic import BaseModel


class NotWorkingConnectionOut(BaseModel):
    station_id: int
    connection_id: int
    operator_id: int | None
    town: str | None
    postcode: str | None
    status_type_id: int | None
    status_title: str | None


class DownConnectionStreakOut(BaseModel):
    station_id: int
    connection_id: int
    operator_id: int | None
    town: str | None
    postcode: str | None
    down_since: date
    days_down: int
