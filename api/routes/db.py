"""
Summoner DB routes – autocomplete, save, stats.
"""
from flask import Blueprint, jsonify, request

from database.summoners import (
    get_summoners_for_autocomplete,
    get_summoner_stats,
    save_summoner,
)

db_bp = Blueprint("db", __name__)


@db_bp.get("/matches")
def cached_matches():
    riot_id = request.args.get("riot_id")
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400
    count = min(int(request.args.get("count", 20)), 100)
    from database.match_cache import get_summoner_profile, get_cached_matches_for_puuid
    profile = get_summoner_profile(riot_id)
    if not profile:
        return jsonify({"riot_id": riot_id, "matches": []})
    matches = get_cached_matches_for_puuid(profile["puuid"], count)
    return jsonify({"riot_id": riot_id, "matches": matches})


@db_bp.get("/match/<match_id>")
def cached_match_detail(match_id: str):
    riot_id = request.args.get("riot_id")
    from database.match_cache import get_match
    from services.match_logic import create_stats_dict, get_player_name, get_game_mode_label
    data = get_match(match_id)
    if not data:
        return jsonify({"error": "Match not in cache"}), 404

    info = data["info"]
    participants = info["participants"]

    focused = None
    if riot_id:
        from database.match_cache import get_summoner_profile
        profile = get_summoner_profile(riot_id)
        if profile:
            puuid = profile["puuid"]
            focused = next((p for p in participants if p.get("puuid") == puuid), None)

    game_duration = info["gameDuration"]
    game_mode = info.get("gameMode", "")

    # derive which teamId won
    blue_win = next((p["win"] for p in participants if p.get("teamId") == 100), False)

    def slim(p):
        return {
            "name": get_player_name(p),
            "champion": p.get("championName", ""),
            "kills": p["kills"],
            "deaths": p["deaths"],
            "assists": p["assists"],
            "win": p["win"],
            "teamId": p["teamId"],
            "totalDamageDealtToChampions": p.get("totalDamageDealtToChampions", 0),
            "cs": p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
            "visionScore": p.get("visionScore", 0),
            "goldEarned": p.get("goldEarned", 0),
            "damageToTurrets": p.get("damageDealtToTurrets", 0),
            "teamPosition": p.get("teamPosition", ""),
            "puuid": p.get("puuid", ""),
        }

    return jsonify({
        "match_id": match_id,
        "game_mode": game_mode,
        "game_mode_label": get_game_mode_label(game_mode),
        "game_duration": game_duration,
        "game_creation": info.get("gameCreation", 0),
        "blue_win": blue_win,
        "participants": [slim(p) for p in participants],
        "focused_stats": create_stats_dict(focused, game_duration) if focused else None,
        "focused_participant": slim(focused) if focused else None,
    })


@db_bp.get("/summoner-stats")
def summoner_stats():
    riot_id = request.args.get("riot_id")
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400
    from database.match_cache import get_summoner_profile, get_summoner_match_stats
    profile = get_summoner_profile(riot_id)
    if not profile:
        return jsonify({"riot_id": riot_id, "total": 0, "top_champions": [], "by_mode": {}})
    return jsonify({"riot_id": riot_id, **get_summoner_match_stats(profile["puuid"])})


@db_bp.get("/summoner-rank")
def summoner_rank():
    """Fetch live rank entries for a summoner from Riot API (cached in Redis 10 min)."""
    riot_id = request.args.get("riot_id")
    region = request.args.get("region", "LAN")
    force = request.args.get("force", "0") == "1"
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    import json
    from database.match_cache import get_summoner_profile, _redis

    cache_key = f"rank:{riot_id}"
    if not force:
        cached = _redis().get(cache_key)
        if cached:
            return jsonify({"riot_id": riot_id, "entries": json.loads(cached)})
    else:
        _redis().delete(cache_key)

    profile = get_summoner_profile(riot_id)
    puuid = (profile or {}).get("puuid")
    if not puuid:
        return jsonify({"riot_id": riot_id, "entries": []})

    from services.riot_api import get_rank_by_puuid_sync
    entries = get_rank_by_puuid_sync(puuid, region)
    try:
        _redis().setex(cache_key, 600, json.dumps(entries))
    except Exception:
        pass
    return jsonify({"riot_id": riot_id, "entries": entries})


@db_bp.get("/summoners/autocomplete")
def autocomplete():
    """
    Query params: q (search string), limit (default 25)
    Returns: { summoners: ["Roga#LAN", ...] }
    """
    q = request.args.get("q", "")
    limit = min(int(request.args.get("limit", 25)), 200)
    summoners = get_summoners_for_autocomplete(q, limit)
    return jsonify({"summoners": summoners})


@db_bp.get("/summoners/with-region")
def summoners_with_region():
    """Returns [{riot_id, region, last_searched, profileIconId, summonerLevel}, ...] for all stored summoners."""
    from database.summoners import get_summoners_with_region
    from database.mongo import get_db
    limit = min(int(request.args.get("limit", 200)), 500)
    pairs = get_summoners_with_region(limit)
    riot_ids = [r for r, _, _ in pairs]

    # Batch-fetch profile icons from summoner_profiles
    db = get_db()
    profiles = {
        doc["_id"]: doc.get("profile", {})
        for doc in db["summoner_profiles"].find(
            {"_id": {"$in": riot_ids}},
            {"_id": 1, "profile.profileIconId": 1, "profile.summonerLevel": 1}
        )
    }

    return jsonify({"summoners": [
        {
            "riot_id": r,
            "region": reg,
            "last_searched": ls.isoformat() if ls else None,
            "profileIconId": profiles.get(r, {}).get("profileIconId"),
            "summonerLevel": profiles.get(r, {}).get("summonerLevel"),
        }
        for r, reg, ls in pairs
    ]})


@db_bp.post("/summoners")
def upsert_summoner():
    """
    Body: { riot_id }
    Increments search_count and updates last_searched.
    Returns 204 on success.
    """
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400
    save_summoner(riot_id)
    return "", 204


@db_bp.get("/stats")
def db_stats():
    """Returns { total_summoners, total_searches }."""
    return jsonify(get_summoner_stats())


@db_bp.get("/sync-progress")
def sync_progress():
    """Returns current sync task progress stored in Redis."""
    import json
    from database.match_cache import _redis
    raw = _redis().get("sync:progress")
    if not raw:
        return jsonify({"status": "idle"})
    return jsonify(json.loads(raw))
