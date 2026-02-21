"""
Pure math for worst-game analysis. No I/O, no Discord.
Migrated unchanged from app/riot/worst_games_analyzer.py.
"""


def calculate_performance_score(participant: dict, match_data: dict) -> float:
    kills = participant["kills"]
    deaths = max(1, participant["deaths"])
    assists = participant["assists"]
    damage = participant["totalDamageDealtToChampions"]
    vision = participant["visionScore"]
    won = participant["win"]

    kda = (kills + assists) / deaths
    kda_score = min(kda * 10, 100)

    team_id = participant["teamId"]
    team = [p for p in match_data["info"]["participants"] if p["teamId"] == team_id]
    team_kills = sum(p["kills"] for p in team)
    kp = ((kills + assists) / max(1, team_kills)) * 100 if team_kills > 0 else 0

    team_damage = sum(p["totalDamageDealtToChampions"] for p in team)
    damage_share = (damage / max(1, team_damage)) * 100 if team_damage > 0 else 0

    duration_min = match_data["info"]["gameDuration"] / 60
    vision_per_min = vision / max(1, duration_min)
    vision_norm = min(vision_per_min * 20, 100)

    score = kda_score * 0.35 + kp * 0.25 + damage_share * 0.25 + vision_norm * 0.15
    if not won:
        score *= 0.8
    return score


def build_match_summary(participant: dict, match_data: dict, match_id: str) -> dict:
    kills = participant["kills"]
    deaths = participant["deaths"]
    assists = participant["assists"]
    damage = participant["totalDamageDealtToChampions"]
    won = participant["win"]
    champion = participant["championName"]
    position = participant.get("teamPosition", "UNKNOWN")
    duration_min = match_data["info"]["gameDuration"] / 60

    kda = (kills + assists) / max(1, deaths)

    team_id = participant["teamId"]
    team = [p for p in match_data["info"]["participants"] if p["teamId"] == team_id]
    team_kills = sum(p["kills"] for p in team)
    kp = ((kills + assists) / max(1, team_kills)) * 100 if team_kills > 0 else 0

    dpm = damage / max(1, duration_min)
    score = calculate_performance_score(participant, match_data)
    timestamp = match_data["info"].get("gameCreation", 0)

    return {
        "match_id": match_id,
        "champion": champion,
        "position": position,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": kda,
        "damage": damage,
        "dpm": dpm,
        "kill_participation": kp,
        "duration_min": duration_min,
        "won": won,
        "score": score,
        "timestamp": timestamp,
    }
