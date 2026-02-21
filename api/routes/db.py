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
    """Returns [{riot_id, region}, ...] for all stored summoners."""
    from database.summoners import get_summoners_with_region
    limit = min(int(request.args.get("limit", 200)), 500)
    pairs = get_summoners_with_region(limit)
    return jsonify({"summoners": [{"riot_id": r, "region": reg} for r, reg in pairs]})


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
