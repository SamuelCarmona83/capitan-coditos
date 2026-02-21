"""
Two-tier cache for Riot match and summoner profile data.

L1  – Redis  (in-memory, survives process restarts but not container restarts)
L2  – MongoDB (persistent, ground truth)

Match data is immutable once a game ends → no TTL on match documents.
Summoner profiles can change (name renames) → 24 h TTL handled by MongoDB TTL index.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional

import redis

from database.mongo import get_db

_redis_client: redis.Redis = None


def init_redis(redis_url: str):
    global _redis_client
    _redis_client = redis.from_url(redis_url, decode_responses=True)


def _redis() -> redis.Redis:
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        init_redis(url)
    return _redis_client


# ---------------------------------------------------------------------------
# Match cache
# ---------------------------------------------------------------------------

def get_match(match_id: str) -> Optional[dict]:
    """Return full match data dict or None.  Checks Redis then MongoDB."""
    # L1 – Redis
    raw = _redis().get(f"match:{match_id}")
    if raw:
        return json.loads(raw)

    # L2 – MongoDB
    doc = get_db()["matches"].find_one({"_id": match_id})
    if doc:
        data = doc["data"]
        # Warm Redis (fire-and-forget, best effort)
        try:
            _redis().set(f"match:{match_id}", json.dumps(data))
        except Exception:
            pass
        return data

    return None


def store_match(match_id: str, data: dict):
    """Persist match data to MongoDB and warm Redis."""
    db = get_db()
    db["matches"].update_one(
        {"_id": match_id},
        {"$setOnInsert": {"_id": match_id, "data": data, "stored_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    try:
        _redis().set(f"match:{match_id}", json.dumps(data))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Summoner profile cache  (PUUID + Summoner V4 profile)
# ---------------------------------------------------------------------------

def get_summoner_profile(riot_id: str) -> Optional[dict]:
    """Return {'puuid': ..., 'profile': {...}} or None."""
    raw = _redis().get(f"puuid:{riot_id}")
    if raw:
        return json.loads(raw)

    doc = get_db()["summoner_profiles"].find_one({"_id": riot_id})
    if doc:
        result = {"puuid": doc["puuid"], "profile": doc["profile"]}
        try:
            _redis().setex(f"puuid:{riot_id}", 86400, json.dumps(result))
        except Exception:
            pass
        return result

    return None


def store_summoner_profile(riot_id: str, puuid: str, profile: dict):
    """Persist summoner profile to MongoDB and warm Redis."""
    db = get_db()
    db["summoner_profiles"].update_one(
        {"_id": riot_id},
        {
            "$set": {
                "puuid": puuid,
                "profile": profile,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    result = {"puuid": puuid, "profile": profile}
    try:
        _redis().setex(f"puuid:{riot_id}", 86400, json.dumps(result))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Match ID index helpers (for prefetch worker)
# ---------------------------------------------------------------------------

def get_cached_match_ids_for_puuid(puuid: str) -> set:
    """Return set of match IDs already stored for this PUUID."""
    db = get_db()
    docs = db["matches"].find(
        {"data.metadata.participants": puuid},
        {"_id": 1},
    )
    return {doc["_id"] for doc in docs}
