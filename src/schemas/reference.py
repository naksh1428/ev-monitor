from pydantic import BaseModel, ConfigDict


class StatusTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    is_operational: bool | None
