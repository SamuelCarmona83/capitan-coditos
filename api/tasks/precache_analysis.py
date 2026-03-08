"""
Celery task: pre-cache heatmap + duration analysis for all summoners.

Runs after sync_all_matches so every summoner's data is warm when
someone opens the dashboard.  Skips any summoner whose cache is
already populated (idempotent).
"""
import asyncio
import os
import time

from tasks.celery_app import celery_app
from database.mongo import init_mongo
from database.match_cache import init_redis


ANALYSIS_COUNT = 20  # matches to analyse per summoner


def _ensure_connections():
    init_mongo(
        os.getenv("MONGO_URL", "mongodb://mongo:27017"),
        os.getenv("MONGO_DB", "capitancoditos"),
    )
    init_redis(os.getenv("REDIS_URL", "redis://redis:6379/0"))


@celery_app.task(name="tasks.precache_analysis.precache_analysis")
def precache_analysis():
    """Pre-cache duration + heatmap analysis for every registered summoner."""
    _ensure_connections()

    async def _run():
        from database.summoners import get_summoners_with_region
        from database.match_cache import get_analysis_cache, set_analysis_cache

        summoner_pairs = get_summoners_with_region(200)
        total = len(summoner_pairs)
        print(f"[precache] Starting analysis pre-cache for {total} summoners")

        cached_count = 0
        computed_count = 0
        errors = 0
        t0 = time.time()

        for idx, (riot_id, region, _ts) in enumerate(summoner_pairs, 1):
            # ── Duration stats ──────────────────────────────────
            try:
                if not get_analysis_cache(riot_id, "duration"):
                    from services.riot_api import get_game_duration_stats

                    buckets, general_stats, summoner_profile = await get_game_duration_stats(
                        riot_id, count=ANALYSIS_COUNT, region=region,
                    )
                    result = {
                        "riot_id": riot_id,
                        "buckets": buckets,
                        "general_stats": general_stats,
                        "summoner_profile": summoner_profile,
                    }
                    set_analysis_cache(riot_id, "duration", result)
                    computed_count += 1
                    print(f"[precache] [{idx}/{total}] {riot_id} duration ✓ (computed)")
                else:
                    cached_count += 1
                    print(f"[precache] [{idx}/{total}] {riot_id} duration ✓ (cached)")
            except Exception as exc:
                errors += 1
                print(f"[precache] [{idx}/{total}] {riot_id} duration ✗ {exc}")

            # ── Heatmap + timeline metrics ──────────────────────
            try:
                if not get_analysis_cache(riot_id, "heatmap"):
                    from services.riot_api import get_position_heatmap_data

                    positions, matches_analyzed, total_frames, metrics, _ = (
                        await get_position_heatmap_data(
                            riot_id, count=ANALYSIS_COUNT, region=region,
                        )
                    )
                    if positions:
                        result = {
                            "riot_id": riot_id,
                            "positions": positions,
                            "matches_analyzed": matches_analyzed,
                            "total_frames": total_frames,
                            "metrics": metrics,
                        }
                        set_analysis_cache(riot_id, "heatmap", result)
                        computed_count += 1
                        print(f"[precache] [{idx}/{total}] {riot_id} heatmap ✓ (computed)")
                    else:
                        print(f"[precache] [{idx}/{total}] {riot_id} heatmap ✗ no positions")
                else:
                    cached_count += 1
                    print(f"[precache] [{idx}/{total}] {riot_id} heatmap ✓ (cached)")
            except Exception as exc:
                errors += 1
                print(f"[precache] [{idx}/{total}] {riot_id} heatmap ✗ {exc}")

        elapsed = time.time() - t0
        print(
            f"[precache] Done in {elapsed:.1f}s — "
            f"computed: {computed_count}, already cached: {cached_count}, errors: {errors}"
        )

    asyncio.run(_run())
