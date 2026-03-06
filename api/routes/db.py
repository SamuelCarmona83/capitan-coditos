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
    count = min(int(request.args.get("count", 20)), 500)
    from database.match_cache import get_summoner_profile, get_cached_matches_for_puuid
    profile = get_summoner_profile(riot_id)
    if not profile:
        return jsonify({"riot_id": riot_id, "matches": []})
    matches = get_cached_matches_for_puuid(profile["puuid"], count)
    return jsonify({"riot_id": riot_id, "matches": matches})


@db_bp.get("/match/<match_id>")
def cached_match_detail(match_id: str):
    riot_id = request.args.get("riot_id")
    from database.match_cache import get_match, get_timeline
    from services.match_logic import create_stats_dict, get_player_name, get_game_mode_label
    data = get_match(match_id)
    if not data:
        return jsonify({"error": "Match not in cache"}), 404

    info = data["info"]
    participants = info["participants"]

    focused = None
    puuid = None
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

    # ── Per-minute timeline metrics for focused player ──
    timeline_metrics = None
    if puuid:
        tl = get_timeline(match_id)
        # If timeline not cached, fetch from Riot API on demand and store it
        if not tl:
            try:
                from services.riot_api import _fetch_timeline_safe_sync
                from database.match_cache import store_timeline
                region = request.args.get("region", "LAN")
                tl = _fetch_timeline_safe_sync(match_id, region)
                if tl:
                    store_timeline(match_id, tl)
            except Exception:
                pass
        if tl:
            try:
                meta_parts = tl.get("metadata", {}).get("participants", [])
                if puuid in meta_parts:
                    p_id = str(meta_parts.index(puuid) + 1)
                    gold, damage, cs = [], [], []
                    for frame in tl.get("info", {}).get("frames", []):
                        pf = frame.get("participantFrames", {}).get(p_id)
                        if not pf:
                            continue
                        gold.append(pf.get("totalGold", 0))
                        dmg_stats = pf.get("damageStats", {})
                        damage.append(dmg_stats.get("totalDamageDoneToChampions", 0))
                        cs.append(pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0))
                    if gold:
                        def _rate(cum):
                            if len(cum) < 2:
                                return cum
                            return [cum[0]] + [max(0, cum[i] - cum[i - 1]) for i in range(1, len(cum))]
                        timeline_metrics = {
                            "gold_cumulative": gold,
                            "gold_per_min": _rate(gold),
                            "damage_cumulative": damage,
                            "damage_per_min": _rate(damage),
                            "cs_cumulative": cs,
                            "cs_per_min": _rate(cs),
                        }
            except Exception:
                pass

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
        "timeline_metrics": timeline_metrics,
    })


@db_bp.get("/summoner-stats")
def summoner_stats():
    riot_id = request.args.get("riot_id")
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400
    from database.match_cache import (
        get_summoner_profile, get_summoner_match_stats,
        get_analysis_cache, set_analysis_cache,
    )

    # Check Redis cache first
    cached = get_analysis_cache(riot_id, "stats")
    if cached:
        return jsonify(cached)

    profile = get_summoner_profile(riot_id)
    if not profile:
        return jsonify({"riot_id": riot_id, "total": 0, "top_champions": [], "by_mode": {}})

    result = {"riot_id": riot_id, **get_summoner_match_stats(profile["puuid"])}
    set_analysis_cache(riot_id, "stats", result)
    return jsonify(result)


@db_bp.get("/analysis-cache")
def analysis_cache():
    """Return cached analysis result without triggering computation.

    Query params:
        riot_id  – summoner riot id (required)
        type     – 'duration' | 'heatmap' (required)
    Returns: { cached: true, result: {...} }  or  { cached: false }
    """
    riot_id = request.args.get("riot_id")
    atype = request.args.get("type")
    if not riot_id or atype not in ("duration", "heatmap"):
        return jsonify({"error": "riot_id and type (duration|heatmap) required"}), 400

    from database.match_cache import get_analysis_cache
    cached = get_analysis_cache(riot_id, atype)
    if cached:
        return jsonify({"cached": True, "result": cached})
    return jsonify({"cached": False})


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


@db_bp.get("/summoner-companions")
def summoner_companions():
    """Return win-rate breakdown vs all known summoners who played on the same team."""
    riot_id = request.args.get("riot_id")
    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    from database.match_cache import get_summoner_profile, get_companion_winrates
    profile = get_summoner_profile(riot_id)
    if not profile:
        return jsonify({"riot_id": riot_id, "companions": []})

    companions = get_companion_winrates(profile["puuid"])
    return jsonify({"riot_id": riot_id, "companions": companions})


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


@db_bp.patch("/summoners/<path:riot_id>/region")
def update_summoner_region(riot_id: str):
    """
    Body: { region }
    Updates the summoner's region, busts the Redis profile cache, and
    re-fetches+stores their Summoner V4 profile from Riot.
    Returns { riot_id, region, profileIconId }.
    """
    data = request.get_json(force=True) or {}
    region = (data.get("region") or "").upper()
    if region not in ("LAN", "LAS", "NA", "EUW", "EUNE", "BR", "KR", "JP",
                      "OCE", "TR", "RU", "PH", "SG", "TH", "TW", "VN"):
        return jsonify({"error": f"Invalid region: {region}"}), 400

    from database.summoners import save_summoner
    from database.match_cache import get_summoner_profile, store_summoner_profile, _redis
    from services.riot_api import get_summoner_data_sync, get_summoner_profile_sync
    from services.match_logic import parse_riot_id

    # 1 – Update region on the summoner document
    save_summoner(riot_id, region=region)

    # 2 – Bust Redis profile + rank cache so stale data is gone immediately
    try:
        _redis().delete(f"puuid:{riot_id}", f"rank:{riot_id}")
    except Exception:
        pass

    # 3 – Re-fetch account + summoner profile from Riot with the new region
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        account = get_summoner_data_sync(game_name, tag_line, region)
        puuid = account["puuid"]
        profile = get_summoner_profile_sync(puuid, region)
        store_summoner_profile(riot_id, puuid, profile)
        icon_id = profile.get("profileIconId")
    except Exception as exc:
        return jsonify({"error": f"Riot API error: {exc}"}), 502

    return jsonify({"riot_id": riot_id, "region": region, "profileIconId": icon_id})


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
