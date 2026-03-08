"""
Celery task: worst-games analysis.
"""
import asyncio
import os

from celery import Task

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(bind=True, name="tasks.worst_games.run_worst_games_task", max_retries=0)
def run_worst_games_task(self: Task, riot_id: str, count: int, region: str, role: str = None):
    _ensure_connections()

    async def _run():
        from services.riot_api import get_worst_performances
        from services.ai import generar_analisis_worst_games
        from services.match_logic import parse_riot_id

        async def progress_callback(current: int, total: int):
            self.update_state(
                state="PROGRESS",
                meta={"current": current, "total": total},
            )

        try:
            worst_games, general_stats, summoner_profile = await get_worst_performances(
                riot_id, count=count, progress_callback=progress_callback,
                region=region, role=role,
            )
        except ValueError as e:
            return {"error": str(e), "riot_id": riot_id}

        game_name = parse_riot_id(riot_id)[0]
        analysis = await generar_analisis_worst_games(game_name, worst_games, general_stats)

        return {
            "riot_id": riot_id,
            "worst_games": worst_games,
            "general_stats": general_stats,
            "summoner_profile": summoner_profile,
            "analysis": analysis,
        }

    return asyncio.run(_run())
