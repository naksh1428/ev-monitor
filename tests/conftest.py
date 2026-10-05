import os

# Settings are read at import time, so these must be set before any app module is imported.
# Real env vars take precedence over .env, so tests never touch the real database or broker.
os.environ.update(
    OCM_API_KEY="test-key",
    DATABASE_URL="mysql+pymysql://test:test@localhost:3306/test",
    COUNTRY_CODE="NL",
    SECRET_KEY="test-secret",
    ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES="30",
    BASE="https://example.invalid/v3/poi",
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from models.models import Base
from utils.db import get_db


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw):
    # SQLite only autoincrements "INTEGER PRIMARY KEY", not BIGINT.
    return "INTEGER"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db_session(db_path):
    """Sync session on a fresh SQLite file database."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_path, db_session):
    """API client whose get_db dependency points at the same SQLite file as db_session."""
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    async_session = async_sessionmaker(bind=async_engine, expire_on_commit=False)

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def make_raw_station(station_id=1, status_type_id=50, connections=None, town="Amsterdam"):
    """Build an OCM-shaped station record."""
    if connections is None:
        connections = [{"ID": station_id * 10, "StatusTypeID": 50, "PowerKW": 22.0}]
    return {
        "ID": station_id,
        "UUID": f"00000000-0000-0000-0000-{station_id:012d}",
        "OperatorID": 7,
        "AddressInfo": {"ID": station_id * 100, "Title": f"Station {station_id}", "Town": town, "Postcode": "1000AA"},
        "NumberOfPoints": len(connections),
        "StatusTypeID": status_type_id,
        "DateCreated": "2024-01-01T10:00:00Z",
        "DateLastStatusUpdate": "2024-06-01T12:00:00+02:00",
        "Connections": connections,
    }
