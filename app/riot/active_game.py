# file: riot/active_game.py - FIXED using Spectator V5 API
import requests
import os
from utils.helpers import make_riot_request, parse_riot_id

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

def get_active_game_by_puuid(puuid, platforms=['la1']):
    """
    Check if a summoner is currently in an active game using Spectator V5 API with PUUID.
    This is the correct solution since V5 accepts PUUID directly!
    """
    for platform in platforms:
        try:
            # Use V5 API that accepts PUUID directly
            url = f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
            headers = {"X-Riot-Token": RIOT_API_KEY}
            
            print(f"[ActiveGame] Checking active game on {platform} using PUUID (V5 API)")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 404:
                print(f"[ActiveGame] No active game found on {platform}")
                continue  # Try next platform
            
            if response.status_code == 200:
                game_data = response.json()
                print(f"[ActiveGame] Found active game on {platform}!")
                return game_data
            
            # For other status codes, log and continue
            print(f"[ActiveGame] Status {response.status_code} on {platform}: {response.text}")
            response.raise_for_status()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                continue  # Expected when not in game
            else:
                print(f"[ActiveGame] HTTP error on {platform}: {e}")
                continue
        except Exception as e:
            print(f"[ActiveGame] Error checking {platform}: {e}")
            continue
    
    # If we get here, no active game found on any platform
    print(f"[ActiveGame] No active game found for PUUID {puuid} on any platform")
    return None


# Keep the old function for backward compatibility, but update it to use V5
def get_active_game_by_summoner_id(summoner_id, platform="la1"):
    """
    Legacy function - now just logs a warning since we don't have summoner IDs
    """
    print(f"[ActiveGame] WARNING: get_active_game_by_summoner_id called but summoner IDs not available in LAN API")
    print(f"[ActiveGame] Use get_active_game_by_puuid instead")
    return None


# Main function that works with your existing code
def get_active_game_by_summoner_data(summoner_data):
    """
    Get active game status using whatever summoner data we have.
    Now uses the V5 API with PUUID!
    """
    puuid = summoner_data.get('puuid')
    
    if not puuid:
        print("[ActiveGame] No PUUID available in summoner data")
        return None
    
    print(f"[ActiveGame] Checking active game for PUUID: {puuid}")
    return get_active_game_by_puuid(puuid)