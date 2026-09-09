from celery import Celery
from celery.schedules import crontab

from utils.config import settings

app = Celery(
    "ev_monitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["api.stations", "services.connection_status"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Station ingest (POST /stations/ingest) is currently triggered on demand, not on
# a schedule; this snapshot should run daily after that day's ingest has completed.
app.conf.beat_schedule = {
    "connection-status-daily-snapshot": {
        "task": "connections.snapshot_daily",
        "schedule": crontab(hour=0, minute=30),
    },
}
