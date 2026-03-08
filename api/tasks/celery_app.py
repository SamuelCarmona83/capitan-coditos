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
        "tasks.heatmap",
        "tasks.precache_analysis",
        "tasks.backfill_timelines",
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
    worker_prefetch_multiplier=1,  # don't pre-claim tasks; lets interactive tasks run immediately
    task_acks_late=True,           # ack only after completion so crashed tasks re-queue
    broker_transport_options={
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
    },
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
        "precache-analysis": {
            "task": "tasks.precache_analysis.precache_analysis",
            "schedule": crontab(hour=3, minute=30, day_of_week=0),  # weekly, Sundays 03:30
        },
        "backfill-timelines": {
            "task": "tasks.backfill_timelines.backfill_timelines",
            "schedule": crontab(hour=4, minute=0),
        },
    },
)


def create_celery(flask_app=None):
    """Optionally bind Celery to a Flask app context (unused but provided for future use)."""
    return celery_app


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Kick off startup tasks. Riot-API-heavy tasks are chained to avoid rate limits."""
    from celery import chain

    celery_app.send_task("tasks.backfill_summoner_ids.backfill_summoner_ids", countdown=10)
    celery_app.send_task("tasks.precache_analysis.precache_analysis", countdown=20)

    # Chain: sync_all_matches → backfill_timelines (sequential to avoid rate limit conflicts)
    chain(
        celery_app.signature("tasks.sync_all_matches.sync_all_matches", countdown=15),
        celery_app.signature("tasks.backfill_timelines.backfill_timelines"),
    ).apply_async()

    print("[startup] Queued backfill_ids (10s), precache (20s), sync→backfill_timelines chain (15s)")
