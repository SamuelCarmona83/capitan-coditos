"""Celery task: game duration distribution analysis."""
import asyncio
import os

from celery import Task

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(bind=True, name="tasks.duration_stats.run_duration_stats_task", max_retries=0)
def run_duration_stats_task(self: Task, riot_id: str, count: int, region: str):
    _ensure_connections()

    async def _run():
        from services.riot_api import get_game_duration_stats
        from database.match_cache import get_analysis_cache, set_analysis_cache

        # Check server-side cache first
        cached = get_analysis_cache(riot_id, "duration")
        if cached:
            return cached

        async def progress_callback(current: int, total: int):
            self.update_state(state="PROGRESS", meta={"current": current, "total": total})

        try:
            buckets, general_stats, summoner_profile = await get_game_duration_stats(
                riot_id, count=count, progress_callback=progress_callback, region=region
            )
        except ValueError as e:
            return {"error": str(e), "riot_id": riot_id}

        result = {
            "riot_id": riot_id,
            "buckets": buckets,
            "general_stats": general_stats,
            "summoner_profile": summoner_profile,
        }

        # Cache successful results
        if "error" not in result:
            set_analysis_cache(riot_id, "duration", result)

        return result

    return asyncio.run(_run())
