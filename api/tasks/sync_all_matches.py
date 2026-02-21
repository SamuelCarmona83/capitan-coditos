import asyncio
import os

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis

SYNC_COUNT = 250


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(name="tasks.sync_all_matches.sync_all_matches")
def sync_all_matches():
    _ensure_connections()

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
            get_match_history_filtered_sync,
            _fetch_match_safe_sync,
        )
        from services.match_logic import parse_riot_id

        summoner_pairs = get_summoners_with_region(200)
        print(f"[sync] Starting 250-match sync for {len(summoner_pairs)} summoners")
        new_stored = 0
        errors = 0

        for riot_id, region, _ts in summoner_pairs:
            try:
                cached = get_summoner_profile(riot_id)
                if cached:
                    puuid = cached["puuid"]
                else:
                    game_name, tag_line = parse_riot_id(riot_id)
                    summoner = get_summoner_data_sync(game_name, tag_line, region)
                    puuid = summoner["puuid"]
                    profile = get_summoner_profile_sync(puuid, region)
                    store_summoner_profile(riot_id, puuid, profile)

                already_cached = get_cached_match_ids_for_puuid(puuid)
                match_ids = []
                for start in range(0, SYNC_COUNT, 100):
                    batch_count = min(100, SYNC_COUNT - start)
                    batch = await asyncio.to_thread(
                        get_match_history_filtered_sync, puuid, batch_count, start, None, None, region
                    )
                    match_ids.extend(batch)
                    if len(batch) < batch_count:
                        break
                    await asyncio.sleep(1.2)

                missing = [m for m in match_ids if m not in already_cached]
                for i, match_id in enumerate(missing):
                    if i > 0:
                        await asyncio.sleep(1.3)
                    data = await asyncio.to_thread(_fetch_match_safe_sync, match_id, region)
                    if data:
                        store_match(match_id, data)
                        new_stored += 1

            except Exception as exc:
                errors += 1
                print(f"[sync] Error processing {riot_id}: {exc}")

        print(f"[sync] Done. New matches stored: {new_stored}, errors: {errors}")

    asyncio.get_event_loop().run_until_complete(_run())
