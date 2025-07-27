import requests
import os
from utils.helpers import make_riot_request, parse_riot_id

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

def get_summoner_data(game_name, tag_line):
    """Fetch summoner data by Riot ID."""
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return make_riot_request(url)

def get_summoner_profile_data(puuid):
    """Fetch summoner profile data from regional API to get profile icon."""
    url = f"https://la1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    return make_riot_request(url)

def get_match_history(puuid, matches=1):
    """Fetch match history by PUUID."""
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={matches}"
    return make_riot_request(url)

def get_match_data(match_id):
    """Fetch match data by match ID."""
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return make_riot_request(url)

async def get_player_match_data(riot_id):
    """Get player's latest match data. Returns (participant, match_data, game_duration, summoner_profile)."""
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = get_summoner_data(game_name, tag_line)
        puuid = summoner['puuid']
        
        # Get summoner profile for icon
        summoner_profile = get_summoner_profile_data(puuid)
        
        matches = get_match_history(puuid)
        if not matches:
            raise ValueError("No se encontraron partidas recientes.")
        
        match_data = get_match_data(matches[0])
        participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
        game_duration = match_data["info"]["gameDuration"] // 60
        
        return participant, match_data, game_duration, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")

async def get_player_multiple_matches(riot_id: str, count: int = 5):
    """Get player's multiple match data. Returns (match_results, summoner_profile)."""
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = get_summoner_data(game_name, tag_line)
        puuid = summoner['puuid']
        
        # Get summoner profile for icon
        summoner_profile = get_summoner_profile_data(puuid)
        
        matches = get_match_history(puuid, matches=count)
        if not matches:
            raise ValueError("No se encontraron partidas recientes.")
        
        match_results = []
        for match_id in matches:
            match_data = get_match_data(match_id)
            participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
            game_duration = match_data["info"]["gameDuration"] // 60
            match_results.append((participant, match_data, game_duration, match_id))
        
        return match_results, summoner_profile
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")
