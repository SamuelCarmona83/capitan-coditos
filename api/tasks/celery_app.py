import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PREFETCH_INTERVAL = int(os.getenv("PREFETCH_INTERVAL_MINUTES", "30"))

celery_app = Celery(
    "capitancoditos",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "tasks.matchups",
        "tasks.worst_games",
        "tasks.prefetch",
        "tasks.duration_stats",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,          # results kept 1 h
    broker_connection_retry_on_startup=True,
    # Beat schedule for the prefetch worker
    beat_schedule={
        "prefetch-matches": {
            "task": "tasks.prefetch.prefetch_matches",
            "schedule": crontab(minute=f"*/{PREFETCH_INTERVAL}"),
        },
    },
)


def create_celery(flask_app=None):
    """Optionally bind Celery to a Flask app context (unused but provided for future use)."""
    return celery_app
