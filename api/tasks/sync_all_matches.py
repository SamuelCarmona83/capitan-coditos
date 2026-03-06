import asyncio
import json
import os
from datetime import datetime, timezone

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis

SYNC_COUNT = 250
PROGRESS_KEY = "sync:progress"


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


def _set_progress(r, **fields):
    """Merge fields into the progress hash stored in Redis."""
    try:
        existing = r.get(PROGRESS_KEY)
        data = json.loads(existing) if existing else {}
        data.update(fields)
        r.setex(PROGRESS_KEY, 3600, json.dumps(data))
    except Exception:
        pass


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
            clear_analysis_cache,
        )
        from services.riot_api import (
            get_summoner_data_sync,
            get_summoner_profile_sync,
            get_match_history_filtered_sync,
            _fetch_match_safe_sync,
        )
        from services.match_logic import parse_riot_id

        summoner_pairs = get_summoners_with_region(200)
        total = len(summoner_pairs)
        print(f"[sync] Starting 250-match sync for {total} summoners")
        new_stored = 0
        errors = 0

        from database.match_cache import _redis
        r = _redis()
        _set_progress(r, status="running", current=0, total=total,
                      new_matches=0, errors=0, current_summoner="",
                      started_at=datetime.now(timezone.utc).isoformat())

        for idx, (riot_id, region, _ts) in enumerate(summoner_pairs, 1):
            _set_progress(r, current=idx, current_summoner=riot_id, new_matches=new_stored, errors=errors)
            try:
                # Always resolve puuid (use cache if available)
                cached = get_summoner_profile(riot_id)
                if cached:
                    puuid = cached["puuid"]
                else:
                    game_name, tag_line = parse_riot_id(riot_id)
                    summoner = get_summoner_data_sync(game_name, tag_line, region)
                    puuid = summoner["puuid"]

                # Always refresh profile data (rank, icon, level)
                profile = get_summoner_profile_sync(puuid, region)
                store_summoner_profile(riot_id, puuid, profile)
                await asyncio.sleep(0.5)  # small pause after profile refresh

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

                # Invalidate cached analysis when new matches were added
                if missing:
                    clear_analysis_cache(riot_id, puuid=puuid)

            except Exception as exc:
                errors += 1
                print(f"[sync] Error processing {riot_id}: {exc}")

        _set_progress(r, status="done", current=total, new_matches=new_stored, errors=errors,
                      current_summoner="", finished_at=datetime.now(timezone.utc).isoformat())
        print(f"[sync] Done. New matches stored: {new_stored}, errors: {errors}")

    asyncio.run(_run())
