import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

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
        "tasks.sync_all_matches",
        "tasks.backfill_summoner_ids",
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
        "sync-all-matches": {
            "task": "tasks.sync_all_matches.sync_all_matches",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


def create_celery(flask_app=None):
    """Optionally bind Celery to a Flask app context (unused but provided for future use)."""
    return celery_app


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Kick off a full match sync and summoner-id backfill shortly after the worker starts."""
    celery_app.send_task("tasks.backfill_summoner_ids.backfill_summoner_ids", countdown=10)
    celery_app.send_task("tasks.sync_all_matches.sync_all_matches", countdown=15)
    print("[startup] Queued backfill_summoner_ids (10s) and sync_all_matches (15s)")
