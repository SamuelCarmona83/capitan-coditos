"""
Celery task: backfill timeline data for matches that don't have it yet.

Fetches match timelines from Riot API and stores them in MongoDB.
Runs in batches with rate-limit pauses to avoid hitting Riot API limits.
Can be triggered manually via POST /api/tasks/backfill-timelines
or scheduled after sync_all_matches.
"""
import asyncio
import os
import time

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis

# How many timelines to fetch per run (avoid very long tasks)
BATCH_SIZE = int(os.getenv("TIMELINE_BACKFILL_BATCH", "200"))


def _ensure_connections():
    init_mongo(
        os.getenv("MONGO_URL", "mongodb://mongo:27017"),
        os.getenv("MONGO_DB", "capitancoditos"),
    )
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(name="tasks.backfill_timelines.backfill_timelines")
def backfill_timelines():
    """Fetch and cache timelines for matches missing them."""
    _ensure_connections()

    from database.mongo import get_db
    from database.match_cache import get_timeline, store_timeline
    from services.riot_api import _fetch_timeline_safe_sync

    db = get_db()

    # Find match IDs that don't have a cached timeline yet
    all_match_ids = [doc["_id"] for doc in db["matches"].find({}, {"_id": 1})]
    cached_tl_ids = set(doc["_id"] for doc in db["timelines"].find({}, {"_id": 1}))
    missing = [mid for mid in all_match_ids if mid not in cached_tl_ids]

    total = len(missing)
    batch = missing[:BATCH_SIZE]
    print(f"[backfill-timelines] {total} matches missing timelines, processing batch of {len(batch)}")

    fetched = 0
    errors = 0
    t0 = time.time()

    for i, match_id in enumerate(batch):
        # Derive region from match_id prefix (e.g. LA1_ → LAN, LA2_ → LAS, NA1_ → NA)
        region = _region_from_match_id(match_id)

        if i > 0:
            time.sleep(1.3)  # Riot rate limit: ~1 req/1.2s

        try:
            tl = _fetch_timeline_safe_sync(match_id, region)
            if tl:
                store_timeline(match_id, tl)
                fetched += 1
            else:
                errors += 1
        except Exception as exc:
            errors += 1
            if i % 50 == 0:
                print(f"[backfill-timelines] Error on {match_id}: {exc}")

        if (i + 1) % 50 == 0:
            print(f"[backfill-timelines] Progress: {i+1}/{len(batch)} (fetched: {fetched}, errors: {errors})")

    elapsed = time.time() - t0
    remaining = total - len(batch)
    print(
        f"[backfill-timelines] Done in {elapsed:.1f}s — "
        f"fetched: {fetched}, errors: {errors}, remaining: {remaining}"
    )


def _region_from_match_id(match_id: str) -> str:
    """Best-effort region from match ID prefix."""
    prefix = match_id.split("_")[0].upper()
    mapping = {
        "LA1": "LAN",
        "LA2": "LAS",
        "NA1": "NA",
        "EUW1": "EUW",
        "EUN1": "EUNE",
        "KR": "KR",
        "JP1": "JP",
        "BR1": "BR",
        "OC1": "OCE",
        "TR1": "TR",
        "RU": "RU",
        "PH2": "PH",
        "SG2": "SG",
        "TH2": "TH",
        "TW2": "TW",
        "VN2": "VN",
    }
    return mapping.get(prefix, "LAN")
