"""
Summoner data routes — fast, synchronous endpoints.
All Riot fetches go through the cache-aside layer.
"""
import asyncio

from flask import Blueprint, jsonify, request

from database.summoners import save_summoner
from services.match_logic import (
    create_stats_dict,
    encontrar_peor_jugador,
    get_game_mode_label,
    is_valid_match_for_analysis,
    parse_riot_id,
    get_champion_icon_url,
    get_summoner_icon_url,
)
from services.riot_api import (
    get_player_match_data,
    get_player_multiple_matches,
    get_active_game_by_puuid_sync,
    _resolve_summoner,
    REGION_MAP,
)

summoner_bp = Blueprint("summoner", __name__)


def _run(coro):
    """Run an async coroutine from a sync Flask handler."""
    return asyncio.get_event_loop().run_until_complete(coro)


@summoner_bp.get("/<riot_id>/last-match")
def last_match(riot_id: str):
    """
    Returns full last-match data + optional AI analysis.
    Query params: region (default LAN), analyze (bool, default true)
    """
    region = request.args.get("region", "LAN")
    do_analyze = request.args.get("analyze", "true").lower() != "false"

    try:
        save_summoner(riot_id, region=region)
        participant, match_data, game_duration, summoner_profile = _run(
            get_player_match_data(riot_id, region)
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    game_name = parse_riot_id(riot_id)[0]
    stats = create_stats_dict(participant, game_duration)
    game_mode = match_data["info"].get("gameMode", "Desconocido")
    valid = is_valid_match_for_analysis(match_data, participant)

    analysis = None
    if do_analyze and valid:
        try:
            from services.ai import generar_mensaje_openai
            analysis = _run(generar_mensaje_openai(game_name, stats, participant, game_mode))
        except Exception as exc:
            analysis = f"[AI error: {exc}]"

    return jsonify({
        "riot_id": riot_id,
        "game_name": game_name,
        "participant": participant,
        "match_data": match_data,
        "game_duration": game_duration,
        "summoner_profile": summoner_profile,
        "stats": stats,
        "game_mode": game_mode,
        "game_mode_label": get_game_mode_label(game_mode),
        "valid_for_analysis": valid,
        "analysis": analysis,
    })


@summoner_bp.get("/<riot_id>/match-history")
def match_history(riot_id: str):
    """
    Returns the last N matches.
    Query params: region (default LAN), count (default 5)
    """
    region = request.args.get("region", "LAN")
    count = min(int(request.args.get("count", 5)), 20)

    try:
        save_summoner(riot_id, region=region)
        match_results, summoner_profile = _run(
            get_player_multiple_matches(riot_id, count, region)
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    matches_out = []
    for participant, match_data, game_duration, match_id in match_results:
        stats = create_stats_dict(participant, game_duration)
        game_mode = match_data["info"].get("gameMode", "Desconocido")
        matches_out.append({
            "match_id": match_id,
            "participant": participant,
            "match_data": match_data,
            "game_duration": game_duration,
            "stats": stats,
            "game_mode": game_mode,
            "game_mode_label": get_game_mode_label(game_mode),
            "valid_for_analysis": is_valid_match_for_analysis(match_data, participant),
        })

    return jsonify({
        "riot_id": riot_id,
        "summoner_profile": summoner_profile,
        "matches": matches_out,
    })


@summoner_bp.get("/<riot_id>/team-analysis")
def team_analysis(riot_id: str):
    """
    Returns last-match data + team breakdown + worst ally + AI analysis.
    Query params: region (default LAN)
    """
    region = request.args.get("region", "LAN")

    try:
        save_summoner(riot_id, region=region)
        participant, match_data, game_duration, summoner_profile = _run(
            get_player_match_data(riot_id, region)
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    game_name = parse_riot_id(riot_id)[0]
    game_mode = match_data["info"].get("gameMode", "Desconocido")
    valid = is_valid_match_for_analysis(match_data, participant)

    allies = [
        p for p in match_data["info"]["participants"]
        if p["teamId"] == participant["teamId"]
    ]

    worst_name, worst_participant, _ = encontrar_peor_jugador(allies)
    worst_stats = create_stats_dict(worst_participant, game_duration)

    analysis = None
    if valid:
        try:
            from services.ai import generar_mensaje_openai
            analysis = _run(generar_mensaje_openai(worst_name, worst_stats, worst_participant, game_mode))
        except Exception as exc:
            analysis = f"[AI error: {exc}]"

    return jsonify({
        "riot_id": riot_id,
        "game_name": game_name,
        "participant": participant,
        "match_data": match_data,
        "game_duration": game_duration,
        "summoner_profile": summoner_profile,
        "game_mode": game_mode,
        "game_mode_label": get_game_mode_label(game_mode),
        "valid_for_analysis": valid,
        "allies": allies,
        "worst_player_name": worst_name,
        "worst_player": worst_participant,
        "worst_player_stats": worst_stats,
        "analysis": analysis,
    })


@summoner_bp.get("/<riot_id>/active-game")
def active_game(riot_id: str):
    """
    Returns spectator V5 data or null if not in game.
    Query params: region (default LAN)
    """
    region = request.args.get("region", "LAN")
    try:
        puuid, _ = _run(_resolve_summoner(riot_id, region))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    import asyncio
    game_data = asyncio.get_event_loop().run_until_complete(
        asyncio.to_thread(get_active_game_by_puuid_sync, puuid, region)
    )
    return jsonify({"in_game": game_data is not None, "game_data": game_data})


@summoner_bp.get("/regions")
def regions():
    return jsonify(list(REGION_MAP.keys()))
