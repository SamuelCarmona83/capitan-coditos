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


def get_cached_matches_for_puuid(puuid: str, count: int = 20) -> list:
    db = get_db()
    docs = (
        db["matches"]
        .find(
            {"data.metadata.participants": puuid},
            {"_id": 1, "data.info.participants": 1, "data.info.gameMode": 1,
             "data.info.queueId": 1, "data.info.gameDuration": 1, "data.info.gameCreation": 1},
        )
        .sort("data.info.gameCreation", -1)
        .limit(count)
    )
    result = []
    for doc in docs:
        info = doc["data"]["info"]
        p = next((x for x in info["participants"] if x.get("puuid") == puuid), None)
        if not p:
            continue
        result.append({
            "match_id": doc["_id"],
            "champion": p.get("championName", ""),
            "kills": p.get("kills", 0),
            "deaths": p.get("deaths", 0),
            "assists": p.get("assists", 0),
            "win": p.get("win", False),
            "game_mode": info.get("gameMode", ""),
            "queue_id": info.get("queueId", 0),
            "game_duration": info.get("gameDuration", 0),
            "game_creation": info.get("gameCreation", 0),
        })
    return result


_QUEUE_MODE = {420: "ranked", 440: "ranked", 450: "aram", 400: "normal", 430: "normal"}


def get_summoner_match_stats(puuid: str) -> dict:
    db = get_db()
    docs = (
        db["matches"]
        .find(
            {"data.metadata.participants": puuid},
            {"_id": 0, "data.info.participants": 1, "data.info.gameMode": 1,
             "data.info.queueId": 1, "data.info.gameDuration": 1},
        )
        .sort("data.info.gameCreation", -1)
        .limit(250)
    )

    total = wins = t_kills = t_deaths = t_assists = t_duration = 0
    champions: dict = {}
    by_mode: dict = {m: {"total": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0}
                     for m in ("ranked", "normal", "aram", "other")}

    for doc in docs:
        info = doc["data"]["info"]
        p = next((x for x in info["participants"] if x.get("puuid") == puuid), None)
        if not p:
            continue
        win = p.get("win", False)
        k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
        total += 1
        if win:
            wins += 1
        t_kills += k; t_deaths += d; t_assists += a
        t_duration += info.get("gameDuration", 0)
        champ = p.get("championName", "")
        if champ:
            c = champions.setdefault(champ, {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0})
            c["games"] += 1
            if win:
                c["wins"] += 1
            c["kills"] += k; c["deaths"] += d; c["assists"] += a
        label = _QUEUE_MODE.get(info.get("queueId", 0), "other")
        bm = by_mode[label]
        bm["total"] += 1
        if win:
            bm["wins"] += 1
        bm["kills"] += k; bm["deaths"] += d; bm["assists"] += a

    def kda(s):
        return round((s["kills"] + s["assists"]) / max(1, s["deaths"]), 2)

    top_champs = sorted(champions.items(), key=lambda x: x[1]["games"], reverse=True)[:8]

    return {
        "total": total,
        "wins": wins,
        "losses": total - wins,
        "winrate": round(wins / total * 100, 1) if total else 0,
        "avg_kda": round((t_kills + t_assists) / max(1, t_deaths), 2) if total else 0,
        "avg_duration": round(t_duration / total) if total else 0,
        "by_mode": {
            k: {
                "total": v["total"],
                "wins": v["wins"],
                "winrate": round(v["wins"] / v["total"] * 100, 1) if v["total"] else 0,
                "avg_kda": kda(v),
            }
            for k, v in by_mode.items()
        },
        "top_champions": [
            {
                "champion": k,
                "games": v["games"],
                "wins": v["wins"],
                "winrate": round(v["wins"] / v["games"] * 100, 1) if v["games"] else 0,
                "avg_kda": kda(v),
            }
            for k, v in top_champs
        ],
    }
