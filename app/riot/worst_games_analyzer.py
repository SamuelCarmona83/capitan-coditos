"""
Analyzer for finding worst game performances.
"""

def calculate_performance_score(participant, match_data):
    """
    Calculate a performance score for a player in a match.
    Lower score = worse performance.
    
    Factors:
    - KDA ratio (normalized)
    - Kill participation
    - Damage share
    - Vision score
    - Win/Loss (losses weighted more heavily)
    """
    kills = participant["kills"]
    deaths = max(1, participant["deaths"])  # Avoid division by zero
    assists = participant["assists"]
    damage = participant["totalDamageDealtToChampions"]
    vision = participant["visionScore"]
    won = participant["win"]
    
    # KDA component (0-100 scale, capped at 10 KDA)
    kda = (kills + assists) / deaths
    kda_score = min(kda * 10, 100)
    
    # Kill participation (percentage of team kills)
    team_id = participant["teamId"]
    team_participants = [p for p in match_data["info"]["participants"] if p["teamId"] == team_id]
    team_kills = sum(p["kills"] for p in team_participants)
    kp = ((kills + assists) / max(1, team_kills)) * 100 if team_kills > 0 else 0
    
    # Damage share (percentage of team damage)
    team_damage = sum(p["totalDamageDealtToChampions"] for p in team_participants)
    damage_share = (damage / max(1, team_damage)) * 100 if team_damage > 0 else 0
    
    # Vision score (normalized, assuming 1 per minute is good)
    game_duration_min = match_data["info"]["gameDuration"] / 60
    vision_per_min = vision / max(1, game_duration_min)
    vision_score_norm = min(vision_per_min * 20, 100)  # Cap at 5 per min
    
    # Weighted composite score
    score = (
        kda_score * 0.35 +      # KDA is most important
        kp * 0.25 +              # Kill participation
        damage_share * 0.25 +    # Damage contribution
        vision_score_norm * 0.15 # Vision
    )
    
    # Penalty for losses (reduce score by 20%)
    if not won:
        score *= 0.8
    
    return score


def build_match_summary(participant, match_data, match_id):
    """Build a summary dict for a match performance."""
    kills = participant["kills"]
    deaths = participant["deaths"]
    assists = participant["assists"]
    damage = participant["totalDamageDealtToChampions"]
    won = participant["win"]
    champion = participant["championName"]
    position = participant.get("teamPosition", "UNKNOWN")
    game_duration_min = match_data["info"]["gameDuration"] / 60
    
    # Calculate KDA
    kda = (kills + assists) / max(1, deaths)
    
    # Kill participation
    team_id = participant["teamId"]
    team_participants = [p for p in match_data["info"]["participants"] if p["teamId"] == team_id]
    team_kills = sum(p["kills"] for p in team_participants)
    kp = ((kills + assists) / max(1, team_kills)) * 100 if team_kills > 0 else 0
    
    # Damage per minute
    dpm = damage / max(1, game_duration_min)
    
    # Performance score
    score = calculate_performance_score(participant, match_data)
    
    # Game timestamp (in milliseconds)
    game_timestamp = match_data["info"].get("gameCreation", 0)
    
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
        "duration_min": game_duration_min,
        "won": won,
        "score": score,
        "timestamp": game_timestamp
    }
