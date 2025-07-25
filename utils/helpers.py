import requests
import os

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

def parse_riot_id(riot_id):
    """Parse and validate Riot ID format."""
    if "#" not in riot_id:
        raise ValueError("El Riot ID debe tener formato `Nombre#Tag` (ej: Roga#LAN)")
    return riot_id.split("#")

def get_player_name(participant):
    """Extract player name from participant data."""
    return (participant.get('riotIdGameName') or 
            participant.get('summonerName') or 
            f"Player_{participant.get('participantId', 'Unknown')}")

def make_riot_request(url):
    """Make a standardized Riot API request with error handling."""
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 404:
        raise ValueError("Summoner not found.")
    elif response.status_code == 429:
        raise ValueError("Rate limit exceeded. Please try again later.")
    
    response.raise_for_status()
    return response.json()

def format_kda(participant):
    """Format KDA string from participant data."""
    return f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"

def get_match_result_info(participant):
    """Get match result and emoji."""
    resultado = "Victoria" if participant["win"] else "Derrota"
    emoji = "🏆" if participant["win"] else "💔"
    return resultado, emoji

def create_stats_dict(participant, game_duration):
    """Create standardized stats dictionary."""
    return {
        "kills": participant["kills"],
        "deaths": participant["deaths"],
        "assists": participant["assists"],
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "gameDuration": game_duration
    }

# Player analysis functions
def encontrar_peor_jugador(participants):
    """Find the worst player in a list of participants."""
    def calcular_score(p):
        k, d, a = p["kills"], p["deaths"], p["assists"]
        damage = p["totalDamageDealtToChampions"]
        return (k + a) / max(1, d) + (damage / 10000)

    scores = {get_player_name(p): calcular_score(p) for p in participants}
    
    if not scores:
        return "Unknown", participants[0], 0
        
    peor_nombre = min(scores, key=scores.get)
    peor_partida = next(p for p in participants if get_player_name(p) == peor_nombre)
    return peor_nombre, peor_partida, scores[peor_nombre]

# Discord utility functions
async def send_long_message(interaction, content):
    """Send long messages by splitting them if they exceed Discord's limit."""
    max_length = 2000
    for i in range(0, len(content), max_length):
        await interaction.followup.send(content[i:i + max_length])

async def handle_command_error(interaction, error):
    """Centralized error handling for commands."""
    if isinstance(error, ValueError):
        await interaction.followup.send(f"⚠️ {str(error)}")
    else:
        await interaction.followup.send(f"❌ Ocurrió un error: {str(error)}")
