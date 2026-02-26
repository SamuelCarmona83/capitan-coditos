"""
Long-running task management routes.

POST /api/tasks/matchups       → enqueue matchups analysis, return task_id
POST /api/tasks/worst-games    → enqueue worst-games analysis, return task_id
GET  /api/tasks/<task_id>      → poll status / collect result
"""
from flask import Blueprint, jsonify, request
from celery.result import AsyncResult

from tasks.celery_app import celery_app

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.post("/matchups")
def start_matchups():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 50))
    region = data.get("region", "LAN")

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    from tasks.matchups import run_matchups_task
    task = run_matchups_task.apply_async(args=[riot_id, count, region])
    return jsonify({"task_id": task.id}), 202


@tasks_bp.post("/worst-games")
def start_worst_games():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 250))
    region = data.get("region", "LAN")
    role = data.get("role", None)

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    from tasks.worst_games import run_worst_games_task
    task = run_worst_games_task.apply_async(args=[riot_id, count, region, role])
    return jsonify({"task_id": task.id}), 202


@tasks_bp.post("/duration-stats")
def start_duration_stats():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 50))
    region = data.get("region", "LAN")
    force = data.get("force", False)

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    if force:
        from database.match_cache import clear_analysis_cache
        clear_analysis_cache(riot_id, "duration")

    from tasks.duration_stats import run_duration_stats_task
    task = run_duration_stats_task.apply_async(args=[riot_id, count, region])
    return jsonify({"task_id": task.id}), 202


@tasks_bp.post("/heatmap")
def start_heatmap():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 20))
    region = data.get("region", "LAN")
    force = data.get("force", False)

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    if force:
        from database.match_cache import clear_analysis_cache
        clear_analysis_cache(riot_id, "heatmap")

    from tasks.heatmap import run_heatmap_task
    task = run_heatmap_task.apply_async(args=[riot_id, count, region])
    return jsonify({"task_id": task.id}), 202


@tasks_bp.post("/precache-analysis")
def start_precache_analysis():
    """Manually trigger pre-caching of duration + heatmap for all summoners."""
    from tasks.precache_analysis import precache_analysis
    task = precache_analysis.apply_async()
    return jsonify({"task_id": task.id}), 202


@tasks_bp.post("/backfill-timelines")
def start_backfill_timelines():
    """Manually trigger backfill of timeline data for matches missing it."""
    from tasks.backfill_timelines import backfill_timelines
    task = backfill_timelines.apply_async()
    return jsonify({"task_id": task.id}), 202


@tasks_bp.get("/<task_id>")
def get_task_status(task_id: str):
    result: AsyncResult = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return jsonify({"status": "PENDING", "progress": None, "result": None})

    if result.state == "PROGRESS":
        meta = result.info or {}
        return jsonify({
            "status": "PROGRESS",
            "progress": {"current": meta.get("current", 0), "total": meta.get("total", 0)},
            "result": None,
        })

    if result.state == "SUCCESS":
        return jsonify({"status": "SUCCESS", "progress": None, "result": result.result})

    if result.state == "FAILURE":
        return jsonify({"status": "FAILURE", "error": str(result.info), "result": None}), 500

    return jsonify({"status": result.state, "progress": None, "result": None})
