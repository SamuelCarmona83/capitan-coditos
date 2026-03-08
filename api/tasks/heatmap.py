"""Celery task: position heatmap analysis via Riot timeline endpoint."""
import asyncio
import os

from celery import Task

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(bind=True, name="tasks.heatmap.run_heatmap_task", max_retries=0)
def run_heatmap_task(self: Task, riot_id: str, count: int, region: str, map_id: int = 11):
    _ensure_connections()

    async def _run():
        from services.riot_api import get_position_heatmap_data
        from database.match_cache import get_analysis_cache, set_analysis_cache

        cache_type = "heatmap_aram" if map_id == 12 else "heatmap"

        # Check server-side cache first
        cached = get_analysis_cache(riot_id, cache_type)
        if cached:
            return cached

        async def progress_callback(current: int, total: int):
            self.update_state(state="PROGRESS", meta={"current": current, "total": total})

        try:
            positions, matches_analyzed, total_frames, metrics, _ = await get_position_heatmap_data(
                riot_id, count=count, progress_callback=progress_callback, region=region, map_id=map_id
            )
        except ValueError as e:
            return {"error": str(e), "riot_id": riot_id}

        if not positions:
            return {"error": "No position data found", "riot_id": riot_id}

        result = {
            "riot_id": riot_id,
            "positions": positions,
            "matches_analyzed": matches_analyzed,
            "total_frames": total_frames,
            "metrics": metrics,
            "map_id": map_id,
        }

        # Cache successful results
        set_analysis_cache(riot_id, cache_type, result)

        return result

    return asyncio.run(_run())
