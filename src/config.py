from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OCM_API_KEY: str
    DATABASE_URL: str
    COUNTRY_CODE: str = "NL"

    class Config:
        env_file = Path(__file__).resolve().parent.parent / ".env"

settings = Settings()