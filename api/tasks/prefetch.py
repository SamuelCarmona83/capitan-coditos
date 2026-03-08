"""
Celery beat task: proactively pre-fetch and cache recent matches
for all summoners in the database.

Runs every PREFETCH_INTERVAL_MINUTES (default 30 min).
"""
import asyncio
import os
import time

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(name="tasks.prefetch.prefetch_matches")
def prefetch_matches():
    _ensure_connections()

    PREFETCH_COUNT = int(os.getenv("PREFETCH_MATCH_COUNT", "20"))

    async def _run():
        from database.summoners import get_summoners_with_region
        from database.match_cache import (
            get_summoner_profile,
            store_summoner_profile,
            get_cached_match_ids_for_puuid,
            store_match,
        )
        from services.riot_api import (
            get_summoner_data_sync,
            get_summoner_profile_sync,
            get_match_history_sync,
            _fetch_match_safe_sync,
        )
        from services.match_logic import parse_riot_id

        summoner_pairs = get_summoners_with_region(200)
        print(f"[prefetch] Starting for {len(summoner_pairs)} summoners, {PREFETCH_COUNT} matches each")
        new_stored = 0
        errors = 0

        for riot_id, region, _ts in summoner_pairs:
            try:
                # Resolve PUUID (use cache if available)
                cached_profile = get_summoner_profile(riot_id)
                if cached_profile:
                    puuid = cached_profile["puuid"]
                else:
                    game_name, tag_line = parse_riot_id(riot_id)
                    summoner = get_summoner_data_sync(game_name, tag_line, region)
                    puuid = summoner["puuid"]
                    profile = get_summoner_profile_sync(puuid, region)
                    store_summoner_profile(riot_id, puuid, profile)

                # Get recent match IDs
                match_ids = await asyncio.to_thread(get_match_history_sync, puuid, PREFETCH_COUNT, region)
                already_cached = get_cached_match_ids_for_puuid(puuid)
                missing = [m for m in match_ids if m not in already_cached]

                # Fetch and store missing matches
                for i, match_id in enumerate(missing):
                    if i > 0:
                        await asyncio.sleep(1.3)  # respect Riot rate limit
                    data = await asyncio.to_thread(_fetch_match_safe_sync, match_id, region)
                    if data:
                        store_match(match_id, data)
                        new_stored += 1

            except Exception as exc:
                errors += 1
                print(f"[prefetch] Error processing {riot_id}: {exc}")

        print(f"[prefetch] Done. New matches stored: {new_stored}, errors: {errors}")
        return {"new_stored": new_stored, "errors": errors}

    return asyncio.run(_run())
