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

def format_champion_name_for_url(champion_name):
    """Format champion name for Data Dragon URL."""
    # Handle special champion names that have different URL formats
    special_cases = {
        "Wukong": "MonkeyKing",
        "Nunu & Willump": "Nunu",
        "Cho'Gath": "Chogath",
        "Kai'Sa": "Kaisa",
        "Kha'Zix": "Khazix",
        "Kog'Maw": "KogMaw",
        "LeBlanc": "Leblanc",
        "Vel'Koz": "Velkoz",
        "Rek'Sai": "RekSai",
        "Renata Glasc": "Renata",
        "Bel'Veth": "Belveth"
    }
    
    return special_cases.get(champion_name, champion_name)

def get_champion_icon_url(champion_name, version="15.14.1"):
    """Get champion icon URL from Data Dragon API."""
    champ_formatted = format_champion_name_for_url(champion_name)
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{champ_formatted}.png"

def get_champion_splash_url(champion_name, skin_num=0):
    """Get champion splash art URL from Data Dragon API."""
    champ_formatted = format_champion_name_for_url(champion_name)
    return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champ_formatted}_{skin_num}.jpg"

def get_match_result_info(participant):
    """Get match result and emoji."""
    resultado = "Victoria" if participant["win"] else "Derrota"
    emoji = "🏆" if participant["win"] else "💔"
    return resultado, emoji

def get_farming_info(participant):
    """Get farming information based on role."""
    role = participant.get('teamPosition', '').upper()
    lane_minions = participant.get('totalMinionsKilled', 0)
    jungle_monsters = participant.get('neutralMinionsKilled', 0)
    
    if role == 'JUNGLE':
        return {
            "primary_farm": jungle_monsters,
            "primary_farm_type": "monstruos de jungla",
            "secondary_farm": lane_minions,
            "secondary_farm_type": "súbditos de carril"
        }
    else:
        return {
            "primary_farm": lane_minions,
            "primary_farm_type": "súbditos de carril",
            "secondary_farm": jungle_monsters,
            "secondary_farm_type": "monstruos de jungla"
        }

def get_role_expectations(participant):
    """Get role-specific expectations for analysis."""
    role = participant.get('teamPosition', '').upper()
    
    expectations = {
        'TOP': {
            'farm_importance': 'alta',
            'farm_target': 150,  # CS esperado a los 20-30 min
            'vision_importance': 'media',
            'damage_importance': 'alta'
        },
        'MIDDLE': {
            'farm_importance': 'alta',
            'farm_target': 150,
            'vision_importance': 'media',
            'damage_importance': 'muy_alta'
        },
        'BOTTOM': {
            'farm_importance': 'muy_alta',
            'farm_target': 180,  # ADC necesita más farm
            'vision_importance': 'baja',
            'damage_importance': 'muy_alta'
        },
        'UTILITY': {  # Support
            'farm_importance': 'muy_baja',
            'farm_target': 30,
            'vision_importance': 'muy_alta',
            'damage_importance': 'baja'
        },
        'JUNGLE': {
            'farm_importance': 'alta',
            'farm_target': 120,  # Monstruos de jungla
            'vision_importance': 'alta',
            'damage_importance': 'alta'
        }
    }
    
    return expectations.get(role, expectations['MIDDLE'])

def create_stats_dict(participant, game_duration):
    """Create standardized stats dictionary with role-specific farming info."""
    farming_info = get_farming_info(participant)
    role_expectations = get_role_expectations(participant)
    
    # Calculate KDA
    kills = participant["kills"]
    deaths = participant["deaths"]
    assists = participant["assists"]
    kda = (kills + assists) / max(1, deaths)
    
    return {
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": kda,
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "gameDuration": game_duration,
        "primary_farm": farming_info["primary_farm"],
        "primary_farm_type": farming_info["primary_farm_type"],
        "secondary_farm": farming_info["secondary_farm"],
        "secondary_farm_type": farming_info["secondary_farm_type"],
        "role_expectations": role_expectations,
        "visionScore": participant.get("visionScore", 0),
        "goldEarned": participant.get("goldEarned", 0),
        "champLevel": participant.get("champLevel", 0),
        "teamPosition": participant.get("teamPosition", "UNKNOWN")
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
