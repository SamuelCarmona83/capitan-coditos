"""
AI analysis routes – thin wrappers around services/ai.py.
"""
import asyncio

from flask import Blueprint, jsonify, request

ai_bp = Blueprint("ai", __name__)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@ai_bp.post("/match-analysis")
def match_analysis():
    """
    Body: { nombre, stats, participant, game_mode }
    Returns: { analysis }
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    stats = data.get("stats")
    participant = data.get("participant", {})
    game_mode = data.get("game_mode", "Desconocido")

    if not nombre or not stats:
        return jsonify({"error": "nombre and stats are required"}), 400

    try:
        from services.ai import generar_mensaje_openai
        analysis = _run(generar_mensaje_openai(nombre, stats, participant, game_mode))
        return jsonify({"analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.post("/matchup-analysis")
def matchup_analysis():
    """
    Body: { nombre, worst_matchups, general_stats }
    worst_matchups: list of [champion_name, data_dict]
    Returns: { analysis }
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    worst_matchups = data.get("worst_matchups", [])
    general_stats = data.get("general_stats", {})

    if not nombre:
        return jsonify({"error": "nombre is required"}), 400

    try:
        from services.ai import generar_analisis_matchups
        analysis = _run(generar_analisis_matchups(nombre, worst_matchups, general_stats))
        return jsonify({"analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.post("/worst-games-analysis")
def worst_games_analysis():
    """
    Body: { nombre, worst_games, general_stats }
    Returns: { analysis }
    """
    data = request.get_json(force=True) or {}
    nombre = data.get("nombre")
    worst_games = data.get("worst_games", [])
    general_stats = data.get("general_stats", {})

    if not nombre:
        return jsonify({"error": "nombre is required"}), 400

    try:
        from services.ai import generar_analisis_worst_games
        analysis = _run(generar_analisis_worst_games(nombre, worst_games, general_stats))
        return jsonify({"analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
