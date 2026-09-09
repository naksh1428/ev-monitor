from datetime import date

from pydantic import BaseModel


class DownConnectionOut(BaseModel):
    connection_id: int
    status_type_id: int | None
    town: str | None
    postcode: str | None
    down_since: date


class DownConnectionStreakOut(BaseModel):
    station_id: int
    connection_id: int
    operator_id: int | None
    town: str | None
    postcode: str | None
    down_since: date
    days_down: int
