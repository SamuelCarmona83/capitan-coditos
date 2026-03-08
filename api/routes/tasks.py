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


def _enqueue(fn, *args, **kwargs):
    """Wrap apply_async so a Redis BusyLoading/Connection error returns 503
    instead of an unhandled 500 — Redis can be momentarily unavailable while
    loading its RDB snapshot after a container restart."""
    try:
        task = fn.apply_async(args=list(args), kwargs=kwargs)
        return jsonify({"task_id": task.id}), 202
    except Exception as exc:
        return jsonify({"error": f"Queue unavailable, please retry: {exc}"}), 503


@tasks_bp.post("/matchups")
def start_matchups():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 50))
    region = data.get("region", "LAN")

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    from tasks.matchups import run_matchups_task
    return _enqueue(run_matchups_task, riot_id, count, region)


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
    return _enqueue(run_worst_games_task, riot_id, count, region, role)


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
    return _enqueue(run_duration_stats_task, riot_id, count, region)


@tasks_bp.post("/heatmap")
def start_heatmap():
    data = request.get_json(force=True) or {}
    riot_id = data.get("riot_id")
    count = int(data.get("count", 20))
    region = data.get("region", "LAN")
    force = data.get("force", False)
    map_id = int(data.get("map_id", 11))

    if not riot_id:
        return jsonify({"error": "riot_id is required"}), 400

    cache_type = "heatmap_aram" if map_id == 12 else "heatmap"
    if force:
        from database.match_cache import clear_analysis_cache
        clear_analysis_cache(riot_id, cache_type)

    from tasks.heatmap import run_heatmap_task
    return _enqueue(run_heatmap_task, riot_id, count, region, map_id)


@tasks_bp.post("/precache-analysis")
def start_precache_analysis():
    """Manually trigger pre-caching of duration + heatmap for all summoners."""
    from tasks.precache_analysis import precache_analysis
    return _enqueue(precache_analysis)


@tasks_bp.post("/backfill-timelines")
def start_backfill_timelines():
    """Manually trigger backfill of timeline data for matches missing it."""
    from tasks.backfill_timelines import backfill_timelines
    return _enqueue(backfill_timelines)


@tasks_bp.get("/<task_id>")
def get_task_status(task_id: str):
    try:
        result: AsyncResult = celery_app.AsyncResult(task_id)
        state = result.state  # this is the call that touches Redis
    except Exception:
        # Redis unavailable (e.g. BusyLoadingError during RDB reload) — tell
        # the client to keep polling; it will resolve once Redis is ready.
        return jsonify({"status": "PENDING", "progress": None, "result": None})

    if state == "PENDING":
        return jsonify({"status": "PENDING", "progress": None, "result": None})

    if state == "PROGRESS":
        meta = result.info or {}
        return jsonify({
            "status": "PROGRESS",
            "progress": {"current": meta.get("current", 0), "total": meta.get("total", 0)},
            "result": None,
        })

    if state == "SUCCESS":
        return jsonify({"status": "SUCCESS", "progress": None, "result": result.result})

    if state == "FAILURE":
        return jsonify({"status": "FAILURE", "error": str(result.info), "result": None}), 500

    return jsonify({"status": state, "progress": None, "result": None})
