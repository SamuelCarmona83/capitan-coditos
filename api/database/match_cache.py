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
# Timeline cache  (immutable, same as match data → no TTL)
# ---------------------------------------------------------------------------

def get_timeline(match_id: str) -> Optional[dict]:
    """Return cached timeline data or None.  Redis L1 → MongoDB L2."""
    key = f"timeline:{match_id}"
    try:
        raw = _redis().get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass

    doc = get_db()["timelines"].find_one({"_id": match_id})
    if doc:
        data = doc["data"]
        try:
            _redis().set(key, json.dumps(data))
        except Exception:
            pass
        return data
    return None


def store_timeline(match_id: str, data: dict):
    """Persist timeline data to MongoDB and warm Redis."""
    db = get_db()
    db["timelines"].update_one(
        {"_id": match_id},
        {"$setOnInsert": {"_id": match_id, "data": data, "stored_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    try:
        _redis().set(f"timeline:{match_id}", json.dumps(data))
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
# Analysis result cache  (Redis-only, with TTL)
# ---------------------------------------------------------------------------

_ANALYSIS_TTL = {
    "stats": 1800,      # 30 min – recomputed from local DB, cheap-ish
    "duration": 21600,  # 6 h   – expensive Riot timeline calls
    "heatmap": 21600,   # 6 h   – expensive Riot timeline calls
}

def get_analysis_cache(riot_id: str, analysis_type: str) -> Optional[dict]:
    """Return cached analysis result or None."""
    key = f"analysis:{analysis_type}:{riot_id}"
    try:
        raw = _redis().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def set_analysis_cache(riot_id: str, analysis_type: str, data: dict, ttl: int = None):
    """Store analysis result in Redis with TTL."""
    key = f"analysis:{analysis_type}:{riot_id}"
    if ttl is None:
        ttl = _ANALYSIS_TTL.get(analysis_type, 3600)
    try:
        _redis().setex(key, ttl, json.dumps(data))
    except Exception:
        pass


def clear_analysis_cache(riot_id: str, analysis_type: str = None, puuid: str = None):
    """Clear analysis caches for a summoner.  If type is None, clear all types.
    Pass puuid to also invalidate the companions cache (only done on full reset).
    """
    try:
        r = _redis()
        types = [analysis_type] if analysis_type else list(_ANALYSIS_TTL.keys())
        for t in types:
            r.delete(f"analysis:{t}:{riot_id}")
        if analysis_type is None and puuid:
            r.delete(f"companions:{puuid}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Companion win-rate cache
# ---------------------------------------------------------------------------

def get_companion_winrates(puuid: str) -> list:
    """Return win-rate stats for every known summoner who played on the same
    team as *puuid*.  Results are cached in Redis for 30 min."""
    cache_key = f"companions:{puuid}"
    try:
        raw = _redis().get(cache_key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass

    db = get_db()

    # Build {puuid -> (riot_id, profileIconId)} map for all registered summoners
    profile_docs = db["summoner_profiles"].find({}, {"_id": 1, "puuid": 1, "profile.profileIconId": 1})
    known = {
        doc["puuid"]: {"riot_id": doc["_id"], "profileIconId": doc.get("profile", {}).get("profileIconId")}
        for doc in profile_docs
        if doc.get("puuid") and doc["puuid"] != puuid
    }

    if not known:
        return []

    # Aggregate per companion across all matches where subject participated
    companions: dict = {}
    for doc in db["matches"].find(
        {"data.metadata.participants": puuid},
        {"data.info.participants": 1},
    ):
        participants = doc["data"]["info"]["participants"]
        subject = next((p for p in participants if p.get("puuid") == puuid), None)
        if not subject:
            continue
        team_id  = subject.get("teamId")
        did_win  = subject.get("win", False)
        for p in participants:
            p_puuid = p.get("puuid", "")
            if p_puuid == puuid or p.get("teamId") != team_id:
                continue
            if p_puuid not in known:
                continue
            riot_id = known[p_puuid]["riot_id"]
            c = companions.setdefault(riot_id, {"games": 0, "wins": 0, "profileIconId": known[p_puuid]["profileIconId"]})
            c["games"] += 1
            if did_win:
                c["wins"] += 1

    result = [
        {
            "riot_id":      riot_id,
            "games":        v["games"],
            "wins":         v["wins"],
            "losses":       v["games"] - v["wins"],
            "win_rate":     round(v["wins"] / v["games"] * 100, 1) if v["games"] else 0,
            "profileIconId": v.get("profileIconId"),
        }
        for riot_id, v in companions.items()
    ]
    result.sort(key=lambda x: x["games"], reverse=True)

    try:
        _redis().setex(cache_key, 1800, json.dumps(result))
    except Exception:
        pass
    return result


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


_QUEUE_MODE = {
    400: "normal",   # Normal Draft
    420: "ranked",   # Ranked Solo/Duo
    430: "normal",   # Normal Blind
    440: "ranked",   # Ranked Flex
    450: "aram",     # ARAM
    480: "normal",   # Swiftplay
    490: "normal",   # Quickplay
    700: "ranked",   # Clash
    720: "aram",     # ARAM Clash
    900: "other",    # ARURF
    1020: "other",   # One for All
    1300: "other",   # Nexus Blitz
    1400: "other",   # Ultimate Spellbook
    1700: "other",   # Arena
    1710: "other",   # Arena (16j)
    1900: "other",   # Pick URF
    2300: "other",   # Brawl
    2400: "aram",    # ARAM: Mayhem
}


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
    )

    total = wins = t_kills = t_deaths = t_assists = t_duration = 0
    champions: dict = {}
    by_mode: dict = {m: {"total": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "duration": 0, "champions": {}}
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
        bm["duration"] += info.get("gameDuration", 0)
        if champ:
            bc = bm["champions"].setdefault(champ, {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0})
            bc["games"] += 1
            if win:
                bc["wins"] += 1
            bc["kills"] += k; bc["deaths"] += d; bc["assists"] += a

    def kda(s):
        return round((s["kills"] + s["assists"]) / max(1, s["deaths"]), 2)

    def top_champs_list(champ_dict, n=8):
        ranked_champs = sorted(champ_dict.items(), key=lambda x: x[1]["games"], reverse=True)[:n]
        return [
            {
                "champion": k,
                "games": v["games"],
                "wins": v["wins"],
                "winrate": round(v["wins"] / v["games"] * 100, 1) if v["games"] else 0,
                "avg_kda": kda(v),
            }
            for k, v in ranked_champs
        ]

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
                "losses": v["total"] - v["wins"],
                "winrate": round(v["wins"] / v["total"] * 100, 1) if v["total"] else 0,
                "avg_kda": kda(v),
                "avg_duration": round(v["duration"] / v["total"]) if v["total"] else 0,
                "top_champions": top_champs_list(v["champions"]),
            }
            for k, v in by_mode.items()
        },
        "top_champions": top_champs_list(champions),
    }
