import os
import time

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


def _ensure_connections():
    init_mongo(os.getenv("MONGO_URL", "mongodb://mongo:27017"), os.getenv("MONGO_DB", "capitancoditos"))
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(name="tasks.backfill_summoner_ids.backfill_summoner_ids")
def backfill_summoner_ids():
    """Fetch and store Summoner V4 profiles for any summoner that has a puuid but is missing
    the encrypted summoner `id` field (needed for rank lookups)."""
    _ensure_connections()

    from database.mongo import get_db
    from database.match_cache import store_summoner_profile, _redis
    from database.summoners import get_summoners_with_region
    from services.riot_api import get_summoner_profile_sync

    db = get_db()

    # Find profiles that exist but are missing `profile.id`
    docs = list(db["summoner_profiles"].find(
        {"$or": [{"profile.id": {"$exists": False}}, {"profile.id": None}]},
        {"_id": 1, "puuid": 1, "profile": 1}
    ))

    # Also include summoners that have no profile document at all
    all_summoners = get_summoners_with_region(500)
    profiled_ids = {doc["_id"] for doc in db["summoner_profiles"].find({}, {"_id": 1})}
    missing_profiles = [(r, reg) for r, reg, _ in all_summoners if r not in profiled_ids]

    print(f"[backfill] {len(docs)} profiles missing summoner id, {len(missing_profiles)} missing profile entirely")
    updated = errors = 0

    # Update existing profiles missing the id
    for doc in docs:
        riot_id = doc["_id"]
        puuid = doc.get("puuid")
        if not puuid:
            continue
        # Determine region from summoners collection
        reg_doc = db["summoners"].find_one({"_id": riot_id}, {"region": 1})
        region = reg_doc.get("region", "LAN") if reg_doc else "LAN"
        try:
            fresh = get_summoner_profile_sync(puuid, region)
            if fresh.get("id"):
                store_summoner_profile(riot_id, puuid, fresh)
                try:
                    _redis().delete(f"rank:{riot_id}")
                except Exception:
                    pass
                updated += 1
                print(f"[backfill] Updated {riot_id}")
        except Exception as e:
            errors += 1
            print(f"[backfill] Error updating {riot_id}: {e}")
        time.sleep(0.5)

    # Fetch profiles for summoners that have none stored
    for riot_id, region in missing_profiles:
        try:
            from services.riot_api import get_summoner_data_sync
            from services.match_logic import parse_riot_id
            game_name, tag_line = parse_riot_id(riot_id)
            summoner = get_summoner_data_sync(game_name, tag_line, region)
            puuid = summoner["puuid"]
            fresh = get_summoner_profile_sync(puuid, region)
            store_summoner_profile(riot_id, puuid, fresh)
            try:
                _redis().delete(f"rank:{riot_id}")
            except Exception:
                pass
            updated += 1
            print(f"[backfill] Created profile for {riot_id}")
        except Exception as e:
            errors += 1
            print(f"[backfill] Error creating profile for {riot_id}: {e}")
        time.sleep(0.8)

    print(f"[backfill] Done. Updated: {updated}, Errors: {errors}")
