from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OCM_API_KEY: str
    DATABASE_URL: str
    COUNTRY_CODE: str = "NL"
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    BASE: str
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        extra = "ignore"  # .env also carries MYSQL_ROOT_PASSWORD, used only by docker-compose's mysql service

settings = Settings()