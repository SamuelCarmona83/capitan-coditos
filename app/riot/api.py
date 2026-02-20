import requests
import os
import time
from utils.helpers import make_riot_request, parse_riot_id

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

# Region mappings for Riot API
# User-friendly region -> (routing_value for account/match APIs, platform_id for summoner/spectator APIs)
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
    """Get (routing_value, platform_id) for a region. Defaults to LAN."""
    region = (region or DEFAULT_REGION).upper()
    if region not in REGION_MAP:
        raise ValueError(f"Invalid region: {region}. Available regions: {', '.join(REGION_MAP.keys())}")
    return REGION_MAP[region]

def get_summoner_data(game_name, tag_line, region=None):
    """Fetch summoner data by Riot ID."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return make_riot_request(url)

def get_summoner_profile_data(puuid, region=None):
    """Fetch summoner profile data from regional API to get profile icon."""
    _, platform = get_region_routing(region)
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return make_riot_request(url)

def get_match_history(puuid, matches=1, region=None):
    """Fetch match history by PUUID."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={matches}"
    return make_riot_request(url)

def get_match_history_filtered(puuid, count=100, start=0, queue=None, match_type=None, region=None):
    """Fetch filtered match history by PUUID."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}"
    if queue:
        url += f"&queue={queue}"
    if match_type:
        url += f"&type={match_type}"
    return make_riot_request(url)

def get_match_data(match_id, region=None):
    """Fetch match data by match ID."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return make_riot_request(url)

def _get_match_data_safe_sync(match_id, region=None):
    """Synchronous fetch match data with retry logic. Returns None on failure."""
    routing, _ = get_region_routing(region)
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 3))
                time.sleep(retry_after + 1)
                continue
            if response.status_code == 404:
                return None
            if response.status_code >= 500:
                time.sleep(2)
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            if attempt == 2:
                return None
            time.sleep(1)
        except requests.exceptions.HTTPError:
            if attempt == 2:
                return None
            time.sleep(1)
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)
    return None

async def get_match_data_safe(match_id, region=None):
    """Async wrapper: fetch match data with retry logic in a thread. Returns None on failure."""
    import asyncio
    return await asyncio.to_thread(_get_match_data_safe_sync, match_id, region)

async def get_player_match_data(riot_id, region=None):
    """Get player's latest match data. Returns (participant, match_data, game_duration, summoner_profile)."""
    import asyncio
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = await asyncio.to_thread(get_summoner_data, game_name, tag_line, region)
        puuid = summoner['puuid']
        
        # Get summoner profile for icon
        summoner_profile = await asyncio.to_thread(get_summoner_profile_data, puuid, region)
        
        matches = await asyncio.to_thread(get_match_history, puuid, 1, region)
        if not matches:
            raise ValueError("No se encontraron partidas recientes.")
        
        match_data = await asyncio.to_thread(get_match_data, matches[0], region)
        participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
        game_duration = match_data["info"]["gameDuration"] // 60
        
        return participant, match_data, game_duration, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")

async def get_player_multiple_matches(riot_id: str, count: int = 5, region=None):
    """Get player's multiple match data. Returns (match_results, summoner_profile)."""
    import asyncio
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = await asyncio.to_thread(get_summoner_data, game_name, tag_line, region)
        puuid = summoner['puuid']
        
        # Get summoner profile for icon
        summoner_profile = await asyncio.to_thread(get_summoner_profile_data, puuid, region)
        
        matches = await asyncio.to_thread(get_match_history, puuid, count, region)
        if not matches:
            raise ValueError("No se encontraron partidas recientes.")
        
        match_results = []
        for match_id in matches:
            match_data = await asyncio.to_thread(get_match_data, match_id, region)
            participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
            game_duration = match_data["info"]["gameDuration"] // 60
            match_results.append((participant, match_data, game_duration, match_id))
        
        return match_results, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")

async def get_player_matchup_data(riot_id: str, count: int = 50, progress_callback=None, region=None):
    """Analyze lane matchup data from ranked games on Summoner's Rift.
    
    Returns (matchups_dict, general_stats, summoner_profile).
    """
    import asyncio
    
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = await asyncio.to_thread(get_summoner_data, game_name, tag_line, region)
        puuid = summoner['puuid']
        summoner_profile = await asyncio.to_thread(get_summoner_profile_data, puuid, region)
        
        # Fetch ranked match IDs (paginate if needed, max 100 per call)
        match_ids = []
        remaining = count
        start = 0
        while remaining > 0:
            batch_size = min(remaining, 100)
            batch = await asyncio.to_thread(
                get_match_history_filtered,
                puuid, batch_size, start, None, "ranked", region
            )
            if not batch:
                break
            match_ids.extend(batch)
            start += batch_size
            remaining -= batch_size
            if len(batch) < batch_size:
                break
        
        if not match_ids:
            raise ValueError("No se encontraron partidas ranked recientes.")
        
        # Process each match to extract matchup data
        matchups = {}
        killers = {}  # Track enemy champions that kill the player the most
        total_analyzed = 0
        total_wins = 0
        roles_played = {}
        champions_played = {}
        errors = 0
        
        for i, match_id in enumerate(match_ids):
            try:
                # Rate limiting: Riot dev keys allow 20 req/sec, 100 req/2min
                # The 2-minute limit is stricter: 100 req / 120 sec = 0.83 req/sec = 1.2 sec/req
                # Sleep 1.3 seconds between each request to stay well under limit
                if i > 0:
                    await asyncio.sleep(1.3)
                
                # Progress callback every ~25 matches
                if progress_callback and i > 0 and i % 25 == 0:
                    await progress_callback(i, len(match_ids))
                
                match_data = await get_match_data_safe(match_id, region=region)
                if not match_data:
                    errors += 1
                    continue
                
                # Only analyze CLASSIC (Summoner's Rift) games
                if match_data["info"].get("gameMode") != "CLASSIC":
                    continue
                
                # Skip remakes
                game_duration = match_data["info"]["gameDuration"] // 60
                if game_duration < 5:
                    continue
                
                # Find the player
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
                
                # Track role and champion stats
                roles_played[player_position] = roles_played.get(player_position, 0) + 1
                if player_champion not in champions_played:
                    champions_played[player_champion] = {"games": 0, "wins": 0}
                champions_played[player_champion]["games"] += 1
                if player_won:
                    champions_played[player_champion]["wins"] += 1
                
                # Track ALL enemy champions' kills (potential killers of the player)
                enemies = [p for p in match_data["info"]["participants"] if p["teamId"] != player_team_id]
                player_deaths = participant["deaths"]
                for enemy in enemies:
                    enemy_champ = enemy["championName"]
                    enemy_kills = enemy["kills"]
                    if enemy_champ not in killers:
                        killers[enemy_champ] = {
                            "games_against": 0,
                            "enemy_kills_total": 0,
                            "player_deaths_in_games": 0,
                            "match_ids": [],  # Store match IDs for linking
                        }
                    killers[enemy_champ]["games_against"] += 1
                    killers[enemy_champ]["enemy_kills_total"] += enemy_kills
                    killers[enemy_champ]["player_deaths_in_games"] += player_deaths
                    # Store match ID (keep last 5 for each champion)
                    if len(killers[enemy_champ]["match_ids"]) < 5:
                        killers[enemy_champ]["match_ids"].append(match_id)
                
                # Find lane opponent (same position, enemy team)
                opponent = next(
                    (p for p in match_data["info"]["participants"]
                     if p["teamId"] != player_team_id and p.get("teamPosition") == player_position),
                    None
                )
                if not opponent:
                    continue
                
                enemy_champion = opponent["championName"]
                
                total_analyzed += 1
                if player_won:
                    total_wins += 1
                
                # Aggregate matchup data
                if enemy_champion not in matchups:
                    matchups[enemy_champion] = {
                        "games": 0, "wins": 0, "losses": 0,
                        "kills": 0, "deaths": 0, "assists": 0,
                        "damage": 0,
                        "player_champions": {}
                    }
                
                m = matchups[enemy_champion]
                m["games"] += 1
                if player_won:
                    m["wins"] += 1
                else:
                    m["losses"] += 1
                m["kills"] += participant["kills"]
                m["deaths"] += participant["deaths"]
                m["assists"] += participant["assists"]
                m["damage"] += participant["totalDamageDealtToChampions"]
                
                # Track what champion the player used against this enemy
                if player_champion not in m["player_champions"]:
                    m["player_champions"][player_champion] = {"games": 0, "wins": 0}
                m["player_champions"][player_champion]["games"] += 1
                if player_won:
                    m["player_champions"][player_champion]["wins"] += 1
                    
            except Exception:
                errors += 1
                # If too many consecutive errors, back off aggressively
                if errors > 5:
                    await asyncio.sleep(3)
                continue
        
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
            "errors": errors
        }
        
        return matchups, general_stats, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")

async def get_worst_performances(riot_id: str, count: int = 250, progress_callback=None, region=None, role=None):
    """
    Analyze ranked games to find worst performances.
    
    Args:
        role: Optional role filter (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY). If specified, only analyzes games in that role.
    
    Returns (worst_games_list, general_stats, summoner_profile).
    Each game has: match_id, champion, position, KDA, damage, score, etc.
    """
    import asyncio
    from riot.worst_games_analyzer import calculate_performance_score, build_match_summary
    
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = await asyncio.to_thread(get_summoner_data, game_name, tag_line, region)
        puuid = summoner['puuid']
        summoner_profile = await asyncio.to_thread(get_summoner_profile_data, puuid, region)
        
        # Fetch ranked match IDs
        match_ids = []
        remaining = count
        start = 0
        while remaining > 0:
            batch_size = min(remaining, 100)
            batch = await asyncio.to_thread(
                get_match_history_filtered,
                puuid, batch_size, start, None, "ranked", region
            )
            if not batch:
                break
            match_ids.extend(batch)
            start += batch_size
            remaining -= batch_size
            if len(batch) < batch_size:
                break
        
        if not match_ids:
            raise ValueError("No se encontraron partidas ranked recientes.")
        
        # Analyze each match
        all_games = []
        roles_played = {}
        champions_played = {}
        total_wins = 0
        errors = 0
        
        for i, match_id in enumerate(match_ids):
            try:
                # Rate limiting
                if i > 0:
                    await asyncio.sleep(1.3)
                
                # Progress callback every 25 matches
                if progress_callback and i > 0 and i % 25 == 0:
                    await progress_callback(i, len(match_ids))
                
                match_data = await get_match_data_safe(match_id, region=region)
                if not match_data:
                    errors += 1
                    continue
                
                # Only CLASSIC games
                if match_data["info"].get("gameMode") != "CLASSIC":
                    continue
                
                # Skip remakes
                game_duration = match_data["info"]["gameDuration"] // 60
                if game_duration < 5:
                    continue
                
                # Find player
                participant = next(
                    (p for p in match_data["info"]["participants"] if p["puuid"] == puuid), None
                )
                if not participant:
                    continue
                
                # Build game summary
                game_summary = build_match_summary(participant, match_data, match_id)
                all_games.append(game_summary)
                
                # Track stats
                position = game_summary["position"]
                champion = game_summary["champion"]
                roles_played[position] = roles_played.get(position, 0) + 1
                if champion not in champions_played:
                    champions_played[champion] = {"games": 0, "wins": 0}
                champions_played[champion]["games"] += 1
                if game_summary["won"]:
                    champions_played[champion]["wins"] += 1
                    total_wins += 1
                    
            except Exception:
                errors += 1
                continue
        
        if not all_games:
            raise ValueError("No se encontraron suficientes partidas ranked en Grieta del Invocador.")
        
        # Filter by role if specified
        if role:
            role_upper = role.upper()
            filtered_games = [g for g in all_games if g["position"] == role_upper]
            if not filtered_games:
                raise ValueError(f"No se encontraron partidas jugadas en el rol {role}.")
            games_to_analyze = filtered_games
        else:
            games_to_analyze = all_games
        
        # Sort by score (lowest = worst performance)
        games_to_analyze.sort(key=lambda g: g["score"])
        worst_games = games_to_analyze[:10]
        
        # Calculate average scores for context (from filtered games if role specified)
        avg_score = sum(g["score"] for g in games_to_analyze) / len(games_to_analyze)
        avg_kda = sum(g["kda"] for g in games_to_analyze) / len(games_to_analyze)
        avg_deaths = sum(g["deaths"] for g in games_to_analyze) / len(games_to_analyze)
        
        general_stats = {
            "total_fetched": len(match_ids),
            "total_analyzed": len(games_to_analyze),
            "total_wins": sum(1 for g in games_to_analyze if g["won"]),
            "total_losses": len(games_to_analyze) - sum(1 for g in games_to_analyze if g["won"]),
            "win_rate": (sum(1 for g in games_to_analyze if g["won"]) / len(games_to_analyze)) * 100,
            "roles_played": roles_played,
            "champions_played": champions_played,
            "avg_score": avg_score,
            "avg_kda": avg_kda,
            "avg_deaths": avg_deaths,
            "errors": errors,
            "filtered_role": role
        }
        
        return worst_games, general_stats, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")
