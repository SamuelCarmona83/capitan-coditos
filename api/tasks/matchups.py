"""
Celery task: matchup analysis.
Runs the full get_player_matchup_data pipeline in a background worker,
reporting progress via Celery task state so the bot can poll it.
"""
import asyncio
import os

from celery import Task

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    """Initialise DB connections inside the worker process."""
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(bind=True, name="tasks.matchups.run_matchups_task", max_retries=0)
def run_matchups_task(self: Task, riot_id: str, count: int, region: str):
    _ensure_connections()

    current_progress = {"value": 0, "total": 0}

    async def _run():
        from services.riot_api import get_player_matchup_data
        from services.ai import generar_analisis_matchups
        from services.match_logic import parse_riot_id

        async def progress_callback(current: int, total: int):
            current_progress["value"] = current
            current_progress["total"] = total
            self.update_state(
                state="PROGRESS",
                meta={"current": current, "total": total},
            )

        try:
            matchup_data, general_stats, summoner_profile = await get_player_matchup_data(
                riot_id, count=count, progress_callback=progress_callback, region=region
            )
        except ValueError as e:
            return {"error": str(e), "riot_id": riot_id}

        # Filter significant matchups (2+ games), sort worst WR first
        significant = {k: v for k, v in matchup_data.items() if v["games"] >= 2} or matchup_data
        worst_matchups = sorted(
            significant.items(),
            key=lambda x: (x[1]["wins"] / x[1]["games"], -x[1]["games"]),
        )[:10]

        game_name = parse_riot_id(riot_id)[0]
        analysis = await generar_analisis_matchups(game_name, worst_matchups, general_stats)

        return {
            "riot_id": riot_id,
            "matchup_data": matchup_data,
            "worst_matchups": [[k, v] for k, v in worst_matchups],
            "general_stats": general_stats,
            "summoner_profile": summoner_profile,
            "analysis": analysis,
        }

    return asyncio.run(_run())
