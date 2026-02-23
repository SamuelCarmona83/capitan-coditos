"""
Riot API service with cache-aside.

All functions that fetch data from Riot first check the cache (Redis→MongoDB).
Match data is immutable, so cache misses are written back.
PUUID / summoner profile has a 24 h TTL.
"""
import asyncio
import os
import time

import requests as _requests

from database.match_cache import (
    get_match,
    store_match,
    get_summoner_profile,
    store_summoner_profile,
)
from services.match_logic import parse_riot_id

RIOT_API_KEY = os.getenv("RIOT_API_KEY", "")

REGION_MAP = {
    "LAN":  ("americas", "la1"),
    "LAS":  ("americas", "la2"),
    "NA":   ("americas", "na1"),
    "BR":   ("americas", "br1"),
    "EUW":  ("europe",   "euw1"),
    "EUNE": ("europe",   "eun1"),
    "TR":   ("europe",   "tr1"),
    "RU":   ("europe",   "ru"),
    "KR":   ("asia",     "kr"),
    "JP":   ("asia",     "jp1"),
    "OCE":  ("sea",      "oc1"),
    "PH":   ("sea",      "ph2"),
    "SG":   ("sea",      "sg2"),
    "TH":   ("sea",      "th2"),
    "TW":   ("sea",      "tw2"),
    "VN":   ("sea",      "vn2"),
}

DEFAULT_REGION = "LAN"


def get_region_routing(region: str = None):
    region = (region or DEFAULT_REGION).upper()
    if region not in REGION_MAP:
        raise ValueError(f"Invalid region: {region}. Available: {', '.join(REGION_MAP)}")
    return REGION_MAP[region]


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------

def _make_riot_request(url: str) -> dict:
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = _requests.get(url, headers=headers, timeout=10)
    if response.status_code == 404:
        raise ValueError("Summoner not found.")
    if response.status_code == 429:
        raise ValueError("Rate limit exceeded. Please try again later.")
    response.raise_for_status()
    return response.json()


def _fetch_match_safe_sync(match_id: str, region: str = None) -> dict | None:
    """Sync fetch with 3 retries. Returns None on permanent failure."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    for attempt in range(3):
        try:
            r = _requests.get(url, headers=headers, timeout=10)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 3)) + 1)
                continue
            if r.status_code == 404:
                return None
            if r.status_code >= 500:
                time.sleep(2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)
    return None


def _fetch_timeline_safe_sync(match_id: str, region: str = None) -> dict | None:
    """Sync fetch match timeline with 3 retries. Returns None on permanent failure."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    for attempt in range(3):
        try:
            r = _requests.get(url, headers=headers, timeout=15)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", 3)) + 1)
                continue
            if r.status_code == 404:
                return None
            if r.status_code >= 500:
                time.sleep(2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Account / summoner lookups  (cache-aware)
# ---------------------------------------------------------------------------

def get_summoner_data_sync(game_name: str, tag_line: str, region: str = None) -> dict:
    routing, _ = get_region_routing(region)
    url = (
        f"https://{routing}.api.riotgames.com/riot/account/v1/accounts"
        f"/by-riot-id/{game_name}/{tag_line}"
    )
    return _make_riot_request(url)


def get_summoner_profile_sync(puuid: str, region: str = None) -> dict:
    _, platform = get_region_routing(region)
    url = (
        f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    )
    return _make_riot_request(url)


def get_rank_sync(summoner_id: str, region: str = None) -> list:
    """Fetch ranked entries by summoner id (legacy). Prefer get_rank_by_puuid_sync."""
    _, platform = get_region_routing(region)
    url = (
        f"https://{platform}.api.riotgames.com/lol/league/v4/entries"
        f"/by-summoner/{summoner_id}"
    )
    try:
        return _make_riot_request(url) or []
    except Exception:
        return []


def get_rank_by_puuid_sync(puuid: str, region: str = None) -> list:
    """Fetch ranked entries by PUUID — works for all accounts including those without summoner id."""
    _, platform = get_region_routing(region)
    url = (
        f"https://{platform}.api.riotgames.com/lol/league/v4/entries"
        f"/by-puuid/{puuid}"
    )
    try:
        return _make_riot_request(url) or []
    except Exception:
        return []


def get_match_history_sync(puuid: str, count: int = 1, region: str = None) -> list:
    routing, _ = get_region_routing(region)
    url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches"
        f"/by-puuid/{puuid}/ids?start=0&count={count}"
    )
    return _make_riot_request(url)


def get_match_history_filtered_sync(
    puuid: str, count: int = 100, start: int = 0,
    queue: str = None, match_type: str = None, region: str = None
) -> list:
    routing, _ = get_region_routing(region)
    url = (
        f"https://{routing}.api.riotgames.com/lol/match/v5/matches"
        f"/by-puuid/{puuid}/ids?start={start}&count={count}"
    )
    if queue:
        url += f"&queue={queue}"
    if match_type:
        url += f"&type={match_type}"
    return _make_riot_request(url)


def get_active_game_by_puuid_sync(puuid: str, region: str = None) -> dict | None:
    _, platform = get_region_routing(region)
    url = (
        f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    )
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = _requests.get(url, headers=headers, timeout=10)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Cached match fetch
# ---------------------------------------------------------------------------

def fetch_match_cached_sync(match_id: str, region: str = None) -> dict | None:
    """Return match data from cache or Riot API, storing on miss."""
    cached = get_match(match_id)
    if cached:
        return cached
    data = _fetch_match_safe_sync(match_id, region)
    if data:
        store_match(match_id, data)
    return data


async def fetch_match_cached(match_id: str, region: str = None) -> dict | None:
    return await asyncio.to_thread(fetch_match_cached_sync, match_id, region)


# ---------------------------------------------------------------------------
# High-level async helpers (used by Flask routes and Celery tasks)
# ---------------------------------------------------------------------------

async def _resolve_summoner(riot_id: str, region: str = None):
    """
    Return (puuid, summoner_profile).
    Uses cache first; writes back on miss.
    """
    cached = get_summoner_profile(riot_id)
    if cached:
        return cached["puuid"], cached["profile"]

    game_name, tag_line = parse_riot_id(riot_id)
    summoner = await asyncio.to_thread(get_summoner_data_sync, game_name, tag_line, region)
    puuid = summoner["puuid"]
    profile = await asyncio.to_thread(get_summoner_profile_sync, puuid, region)
    store_summoner_profile(riot_id, puuid, profile)
    return puuid, profile


async def get_player_match_data(riot_id: str, region: str = None):
    """Returns (participant, match_data, game_duration_min, summoner_profile)."""
    puuid, summoner_profile = await _resolve_summoner(riot_id, region)
    match_ids = await asyncio.to_thread(get_match_history_sync, puuid, 1, region)
    if not match_ids:
        raise ValueError("No se encontraron partidas recientes.")
    match_data = await fetch_match_cached(match_ids[0], region)
    if not match_data:
        raise ValueError("No se pudo obtener la partida.")
    participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
    game_duration = match_data["info"]["gameDuration"] // 60
    return participant, match_data, game_duration, summoner_profile


async def get_player_multiple_matches(riot_id: str, count: int = 5, region: str = None):
    """Returns (match_results, summoner_profile).
    match_results = [(participant, match_data, game_duration_min, match_id), ...]
    """
    puuid, summoner_profile = await _resolve_summoner(riot_id, region)
    match_ids = await asyncio.to_thread(get_match_history_sync, puuid, count, region)
    if not match_ids:
        raise ValueError("No se encontraron partidas recientes.")
    match_results = []
    for mid in match_ids:
        match_data = await fetch_match_cached(mid, region)
        if not match_data:
            continue
        participant = next(
            (p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None
        )
        if not participant:
            continue
        duration = match_data["info"]["gameDuration"] // 60
        match_results.append((participant, match_data, duration, mid))
    return match_results, summoner_profile


async def get_player_matchup_data(
    riot_id: str, count: int = 50, progress_callback=None, region: str = None
):
    """Returns (matchups_dict, general_stats, summoner_profile).
    progress_callback: async callable(current: int, total: int) or None.
    """
    puuid, summoner_profile = await _resolve_summoner(riot_id, region)

    # Fetch match ID list – paginate if needed
    match_ids = []
    remaining = count
    start = 0
    while remaining > 0:
        batch = min(remaining, 100)
        ids = await asyncio.to_thread(
            get_match_history_filtered_sync, puuid, batch, start, None, "ranked", region
        )
        if not ids:
            break
        match_ids.extend(ids)
        start += batch
        remaining -= batch
        if len(ids) < batch:
            break

    if not match_ids:
        raise ValueError("No se encontraron partidas ranked recientes.")

    # Get the set of already-cached match IDs to skip the sleep
    from database.match_cache import get_cached_match_ids_for_puuid
    cached_ids = get_cached_match_ids_for_puuid(puuid)

    matchups = {}
    killers = {}
    total_analyzed = 0
    total_wins = 0
    roles_played = {}
    champions_played = {}
    errors = 0

    for i, match_id in enumerate(match_ids):
        try:
            needs_riot_fetch = match_id not in cached_ids
            if needs_riot_fetch and i > 0:
                await asyncio.sleep(1.3)

            if progress_callback and i > 0 and i % 25 == 0:
                await progress_callback(i, len(match_ids))

            match_data = await fetch_match_cached(match_id, region)
            if not match_data:
                errors += 1
                continue

            if match_data["info"].get("gameMode") != "CLASSIC":
                continue
            if match_data["info"]["gameDuration"] // 60 < 5:
                continue

            participant = next(
                (p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None
            )
            if not participant:
                continue

            player_position = participant.get("teamPosition", "")
            if not player_position:
                continue

            player_team_id = participant["teamId"]
            player_champion = participant["championName"]
            player_won = participant["win"]

            roles_played[player_position] = roles_played.get(player_position, 0) + 1
            if player_champion not in champions_played:
                champions_played[player_champion] = {"games": 0, "wins": 0}
            champions_played[player_champion]["games"] += 1
            if player_won:
                champions_played[player_champion]["wins"] += 1

            enemies = [p for p in match_data["info"]["participants"] if p["teamId"] != player_team_id]
            player_deaths = participant["deaths"]
            for enemy in enemies:
                ec = enemy["championName"]
                if ec not in killers:
                    killers[ec] = {"games_against": 0, "enemy_kills_total": 0, "player_deaths_in_games": 0, "match_ids": []}
                killers[ec]["games_against"] += 1
                killers[ec]["enemy_kills_total"] += enemy["kills"]
                killers[ec]["player_deaths_in_games"] += player_deaths
                if len(killers[ec]["match_ids"]) < 5:
                    killers[ec]["match_ids"].append(match_id)

            opponent = next(
                (p for p in match_data["info"]["participants"]
                 if p["teamId"] != player_team_id and p.get("teamPosition") == player_position),
                None,
            )
            if not opponent:
                continue

            enemy_champion = opponent["championName"]
            total_analyzed += 1
            if player_won:
                total_wins += 1

            if enemy_champion not in matchups:
                matchups[enemy_champion] = {
                    "games": 0, "wins": 0, "losses": 0,
                    "kills": 0, "deaths": 0, "assists": 0,
                    "damage": 0, "player_champions": {},
                }
            m = matchups[enemy_champion]
            m["games"] += 1
            m["wins" if player_won else "losses"] += 1
            m["kills"] += participant["kills"]
            m["deaths"] += participant["deaths"]
            m["assists"] += participant["assists"]
            m["damage"] += participant["totalDamageDealtToChampions"]
            if player_champion not in m["player_champions"]:
                m["player_champions"][player_champion] = {"games": 0, "wins": 0}
            m["player_champions"][player_champion]["games"] += 1
            if player_won:
                m["player_champions"][player_champion]["wins"] += 1

        except Exception:
            errors += 1
            if errors > 5:
                await asyncio.sleep(3)

    if total_analyzed == 0:
        raise ValueError(
            "No se encontraron suficientes partidas ranked en Grieta del Invocador para analizar matchups."
        )

    general_stats = {
        "total_fetched": len(match_ids),
        "total_analyzed": total_analyzed,
        "total_wins": total_wins,
        "total_losses": total_analyzed - total_wins,
        "win_rate": (total_wins / total_analyzed) * 100,
        "roles_played": roles_played,
        "champions_played": champions_played,
        "killers": killers,
        "errors": errors,
    }
    return matchups, general_stats, summoner_profile


async def get_worst_performances(
    riot_id: str, count: int = 250, progress_callback=None, region: str = None, role: str = None
):
    """Returns (worst_games_list, general_stats, summoner_profile)."""
    from services.worst_games_analyzer import build_match_summary

    puuid, summoner_profile = await _resolve_summoner(riot_id, region)

    match_ids = []
    remaining = count
    start = 0
    while remaining > 0:
        batch = min(remaining, 100)
        ids = await asyncio.to_thread(
            get_match_history_filtered_sync, puuid, batch, start, None, "ranked", region
        )
        if not ids:
            break
        match_ids.extend(ids)
        start += batch
        remaining -= batch
        if len(ids) < batch:
            break

    if not match_ids:
        raise ValueError("No se encontraron partidas ranked recientes.")

    from database.match_cache import get_cached_match_ids_for_puuid
    cached_ids = get_cached_match_ids_for_puuid(puuid)

    all_games = []
    roles_played = {}
    champions_played = {}
    total_wins = 0
    errors = 0

    for i, match_id in enumerate(match_ids):
        try:
            if match_id not in cached_ids and i > 0:
                await asyncio.sleep(1.3)
            if progress_callback and i > 0 and i % 25 == 0:
                await progress_callback(i, len(match_ids))

            match_data = await fetch_match_cached(match_id, region)
            if not match_data:
                errors += 1
                continue

            if match_data["info"].get("gameMode") != "CLASSIC":
                continue
            if match_data["info"]["gameDuration"] // 60 < 5:
                continue

            participant = next(
                (p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None
            )
            if not participant:
                continue

            summary = build_match_summary(participant, match_data, match_id)
            all_games.append(summary)

            pos = summary["position"]
            champ = summary["champion"]
            roles_played[pos] = roles_played.get(pos, 0) + 1
            if champ not in champions_played:
                champions_played[champ] = {"games": 0, "wins": 0}
            champions_played[champ]["games"] += 1
            if summary["won"]:
                champions_played[champ]["wins"] += 1
                total_wins += 1

        except Exception:
            errors += 1

    if not all_games:
        raise ValueError("No se encontraron suficientes partidas ranked en Grieta del Invocador.")

    if role and role.upper() != "ALL":
        role_upper = role.upper()
        all_games = [g for g in all_games if g["position"] == role_upper]
        if not all_games:
            raise ValueError(f"No se encontraron partidas jugadas en el rol {role}.")

    all_games.sort(key=lambda g: g["score"])
    worst_games = all_games[:10]

    general_stats = {
        "total_fetched": len(match_ids),
        "total_analyzed": len(all_games),
        "total_wins": sum(1 for g in all_games if g["won"]),
        "total_losses": len(all_games) - sum(1 for g in all_games if g["won"]),
        "win_rate": (sum(1 for g in all_games if g["won"]) / len(all_games)) * 100,
        "roles_played": roles_played,
        "champions_played": champions_played,
        "avg_score": sum(g["score"] for g in all_games) / len(all_games),
        "avg_kda": sum(g["kda"] for g in all_games) / len(all_games),
        "avg_deaths": sum(g["deaths"] for g in all_games) / len(all_games),
        "errors": errors,
        "filtered_role": role,
    }
    return worst_games, general_stats, summoner_profile


# ---------------------------------------------------------------------------
# Game duration distribution
# ---------------------------------------------------------------------------

async def get_game_duration_stats(riot_id: str, count: int = 50,
                                   progress_callback=None, region: str = None):
    """Analyse game duration distribution. Returns (buckets, general_stats, summoner_profile)."""
    BUCKET_DEFS = [
        {"label": "≤15 min",  "max": 15},
        {"label": "15–20 min", "max": 20},
        {"label": "20–25 min", "max": 25},
        {"label": "25–30 min", "max": 30},
        {"label": ">30 min",   "max": None},
    ]

    puuid, summoner_profile = await _resolve_summoner(riot_id, region)

    # Paginate match IDs (all queues)
    match_ids: list[str] = []
    remaining = count
    start = 0
    while remaining > 0:
        batch_size = min(remaining, 100)
        batch = await asyncio.to_thread(
            get_match_history_filtered_sync, puuid, batch_size, start, None, None, region
        )
        if not batch:
            break
        match_ids.extend(batch)
        start += batch_size
        remaining -= batch_size
        if len(batch) < batch_size:
            break

    if not match_ids:
        raise ValueError("No se encontraron partidas recientes.")

    buckets = [
        {"label": b["label"], "max": b["max"], "total": 0, "wins": 0, "losses": 0}
        for b in BUCKET_DEFS
    ]

    total_fetched = len(match_ids)
    total_analyzed = 0
    total_wins = 0
    errors = 0
    skipped_remakes = 0
    total_duration_sec = 0.0

    for i, match_id in enumerate(match_ids):
        if progress_callback:
            await progress_callback(i + 1, total_fetched)
        try:
            match_data = await fetch_match_cached(match_id, region)
            if not match_data:
                errors += 1
                continue

            duration_sec = match_data["info"].get("gameDuration", 0)
            duration_min = duration_sec / 60.0

            if duration_min < 5:
                skipped_remakes += 1
                continue

            participant = next(
                (p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None
            )
            if not participant:
                errors += 1
                continue

            won = participant.get("win", False)
            total_analyzed += 1
            total_duration_sec += duration_sec
            if won:
                total_wins += 1

            prev_max = 0
            for bucket in buckets:
                upper = bucket["max"]
                if upper is None or duration_min < upper:
                    if duration_min >= prev_max:
                        bucket["total"] += 1
                        if won:
                            bucket["wins"] += 1
                        else:
                            bucket["losses"] += 1
                        break
                prev_max = upper if upper else prev_max

        except Exception:
            errors += 1

    if total_analyzed == 0:
        raise ValueError("No hay partidas válidas para analizar.")

    for bucket in buckets:
        bucket["pct"] = (bucket["total"] / total_analyzed) * 100
        bucket["win_pct"] = (bucket["wins"] / bucket["total"] * 100) if bucket["total"] else 0
        bucket["loss_pct"] = (bucket["losses"] / bucket["total"] * 100) if bucket["total"] else 0

    general_stats = {
        "total_fetched": total_fetched,
        "total_analyzed": total_analyzed,
        "skipped_remakes": skipped_remakes,
        "errors": errors,
        "total_wins": total_wins,
        "total_losses": total_analyzed - total_wins,
        "win_rate": (total_wins / total_analyzed) * 100,
        "avg_duration_min": (total_duration_sec / total_analyzed) / 60.0,
    }
    return buckets, general_stats, summoner_profile


# ---------------------------------------------------------------------------
# Position heatmap data  (timeline endpoint)
# ---------------------------------------------------------------------------

async def get_position_heatmap_data(
    riot_id: str, count: int = 20, progress_callback=None, region: str = None
):
    """Fetch position data + per-minute metrics across multiple matches.

    Returns (positions, matches_analyzed, total_frames, metrics, summoner_profile).
    ``positions`` is a flat list of [x, y] pairs (game coordinates 0–14820).
    ``metrics`` contains gold/damage/cs cumulative and per-minute rate averages.
    Only Summoner's Rift (mapId 11) games with duration ≥ 5 min are included.
    """
    puuid, summoner_profile = await _resolve_summoner(riot_id, region)

    # Paginate match IDs (all queues)
    match_ids: list[str] = []
    remaining = count
    start = 0
    while remaining > 0:
        batch_size = min(remaining, 100)
        batch = await asyncio.to_thread(
            get_match_history_filtered_sync, puuid, batch_size, start,
            queue=None, match_type=None, region=region,
        )
        if not batch:
            break
        match_ids.extend(batch)
        start += batch_size
        remaining -= batch_size
        if len(batch) < batch_size:
            break

    if not match_ids:
        raise ValueError("No matches found.")

    positions: list[list[int]] = []
    matches_analyzed = 0
    errors = 0

    # Per-minute metric accumulators (one list per match)
    gold_per_min_series: list[list[int]] = []
    damage_per_min_series: list[list[int]] = []
    cs_per_min_series: list[list[int]] = []

    for i, match_id in enumerate(match_ids):
        if progress_callback and i % 3 == 0:
            await progress_callback(i, len(match_ids))

        try:
            # Use cached match data to filter non-SR games before timeline call
            match_data = await fetch_match_cached(match_id, region)
            if not match_data:
                errors += 1
                continue

            info = match_data.get("info", {})
            if info.get("mapId") != 11:
                continue  # Skip non-Summoner's Rift
            if info.get("gameDuration", 0) < 300:
                continue  # Skip remakes (< 5 min)

            # Check timeline cache first, then Riot API
            from database.match_cache import get_timeline, store_timeline
            timeline = get_timeline(match_id)
            if not timeline:
                # Rate limit before timeline API call
                if matches_analyzed > 0:
                    await asyncio.sleep(1.3)

                timeline = await asyncio.to_thread(
                    _fetch_timeline_safe_sync, match_id, region
                )
                if not timeline:
                    errors += 1
                    continue
                # Persist for future use
                store_timeline(match_id, timeline)

            # Map puuid → participantId via timeline metadata
            meta_parts = timeline.get("metadata", {}).get("participants", [])
            if puuid not in meta_parts:
                continue
            p_id = str(meta_parts.index(puuid) + 1)

            match_gold = []
            match_damage = []
            match_cs = []

            for frame in timeline.get("info", {}).get("frames", []):
                pf = frame.get("participantFrames", {}).get(p_id)
                if not pf:
                    continue
                if "position" in pf:
                    positions.append([pf["position"]["x"], pf["position"]["y"]])
                # Per-minute metrics (cumulative values from Riot)
                match_gold.append(pf.get("totalGold", 0))
                dmg_stats = pf.get("damageStats", {})
                match_damage.append(dmg_stats.get("totalDamageDoneToChampions", 0))
                match_cs.append(
                    pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0)
                )

            if match_gold:
                gold_per_min_series.append(match_gold)
                damage_per_min_series.append(match_damage)
                cs_per_min_series.append(match_cs)

            matches_analyzed += 1

        except Exception:
            errors += 1
            if errors > 5:
                await asyncio.sleep(3)

    # ── Compute averaged per-minute curves ────────────────────────
    def _average_series(series_list: list[list[int]]) -> list[int]:
        if not series_list:
            return []
        max_len = max(len(s) for s in series_list)
        result = []
        for minute in range(max_len):
            vals = [s[minute] for s in series_list if minute < len(s)]
            result.append(round(sum(vals) / len(vals)) if vals else 0)
        return result

    def _to_per_minute_rate(cumulative: list[int]) -> list[int]:
        if len(cumulative) < 2:
            return cumulative
        return [cumulative[0]] + [
            max(0, cumulative[i] - cumulative[i - 1])
            for i in range(1, len(cumulative))
        ]

    avg_gold = _average_series(gold_per_min_series)
    avg_damage = _average_series(damage_per_min_series)
    avg_cs = _average_series(cs_per_min_series)

    metrics = {
        "gold_cumulative": avg_gold,
        "gold_per_min": _to_per_minute_rate(avg_gold),
        "damage_cumulative": avg_damage,
        "damage_per_min": _to_per_minute_rate(avg_damage),
        "cs_cumulative": avg_cs,
        "cs_per_min": _to_per_minute_rate(avg_cs),
    }

    return positions, matches_analyzed, len(positions), metrics, summoner_profile
