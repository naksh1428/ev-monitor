
from pydantic import BaseModel, ConfigDict

class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    website: str | None