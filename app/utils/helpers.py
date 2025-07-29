import requests
import os
import discord

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

# Import here to avoid circular imports
def _import_get_player_match_data():
    from riot.api import get_player_match_data
    return get_player_match_data

def _import_get_player_multiple_matches():
    from riot.api import get_player_multiple_matches
    return get_player_multiple_matches

def _import_generar_mensaje_openai():
    from ai.openai_service import generar_mensaje_openai
    return generar_mensaje_openai

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

def is_valid_match_for_analysis(match_data, participant):
    """Check if a match is valid for AI analysis (not a remake or very short game)."""
    game_duration_seconds = match_data["info"]["gameDuration"]
    game_duration_minutes = game_duration_seconds // 60
    
    # Check for remake conditions
    # 1. Very short games (less than 5 minutes are usually remakes)
    if game_duration_minutes < 5:
        return False
    
    # 2. Check if game ended in early surrender (remake)
    game_ended_early = match_data["info"].get("gameEndedInEarlySurrender", False)
    if game_ended_early:
        return False
    
    # 3. Check for extremely low stats that suggest a remake
    # In remakes, players usually have very low kills, deaths, and damage
    total_damage = participant.get("totalDamageDealtToChampions", 0)
    kills = participant.get("kills", 0)
    deaths = participant.get("deaths", 0)
    assists = participant.get("assists", 0)
    
    # If all stats are extremely low, it's likely a remake
    if (total_damage < 500 and kills == 0 and deaths <= 1 and assists == 0 and 
        game_duration_minutes < 8):
        return False
    
    return True

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

def get_summoner_icon_url(profile_icon_id, version="15.14.1"):
    """Get summoner profile icon URL from Data Dragon API."""
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{profile_icon_id}.png"

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

# Common match analysis functions
async def get_match_analysis_data(riot_id: str):
    """Get common match analysis data used by both commands"""
    get_player_match_data = _import_get_player_match_data()
    participant, match_data, game_duration, summoner_profile = await get_player_match_data(riot_id)
    game_name = parse_riot_id(riot_id)[0]
    
    stats = create_stats_dict(participant, game_duration)
    game_mode = match_data["info"]["gameMode"] or "Desconocido"
    
    return participant, match_data, game_duration, game_name, stats, game_mode, summoner_profile

async def create_ultima_partida_embed(riot_id: str):
    """Create a complete ultima partida embed with AI analysis"""
    # Get match data
    participant, match_data, game_duration, game_name, stats, game_mode, summoner_profile = await get_match_analysis_data(riot_id)
    
    # Check if match is valid for analysis
    if not is_valid_match_for_analysis(match_data, participant):
        # Create embed without AI analysis for remake/very short games
        return await create_simple_match_embed(riot_id, participant, match_data, game_duration, summoner_profile)
    
    # Generate AI analysis for valid matches
    generar_mensaje_openai = _import_generar_mensaje_openai()
    mensaje_openai = await generar_mensaje_openai(game_name, stats, participant, game_mode)
    
    # Create embed
    return await create_match_analysis_embed(riot_id, participant, match_data, game_duration, mensaje_openai, summoner_profile)

async def create_match_history_embed(riot_id: str, match_results, summoner_profile=None):
    """Create embed showing multiple matches with summary"""
    game_name = parse_riot_id(riot_id)[0]
    
    # Calculate overall stats
    total_wins = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    
    match_summaries = []
    for i, (participant, match_data, game_duration, match_id) in enumerate(match_results):
        champ = participant["championName"]
        kda_str = format_kda(participant)
        resultado, emoji = get_match_result_info(participant)
        
        if resultado == "Victoria":
            total_wins += 1
        
        total_kills += participant["kills"]
        total_deaths += participant["deaths"] 
        total_assists += participant["assists"]
        
        # Custom mapping for game mode names
        game_mode = match_data["info"]["gameMode"] or "Desconocido"
        custom_game_modes = {
            "CLASSIC": "Grieta",
            "ARAM": "ARAM",
            "URF": "URF",
            "CHERRY": "Arena"
        }
        game_mode_name = custom_game_modes.get(game_mode, game_mode)
        
        match_summaries.append(f"`{i+1}.` {emoji} **{champ}** - {kda_str} | {game_mode_name} ({game_duration}min)")
    
    # Calculate win rate and average KDA
    win_rate = (total_wins / len(match_results)) * 100
    avg_kda = (total_kills + total_assists) / max(1, total_deaths)
    
    # Create embed
    embed = discord.Embed(
        title=f"Historial de {riot_id} (Últimas {len(match_results)} partidas)",
        description=f"🏆 **{win_rate:.0f}% WR** | 📊 **{avg_kda:.1f} KDA promedio**",
        color=0x00ff00 if win_rate >= 50 else 0xff9900 if win_rate >= 30 else 0xff0000
    )
    
    embed.add_field(
        name="📋 Partidas recientes:",
        value="\n".join(match_summaries),
        inline=False
    )
    
    # Set summoner profile icon if available
    if summoner_profile:
        profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
        embed.set_author(name=f"Nivel {summoner_profile['summonerLevel']}", icon_url=profile_icon_url)
    
    embed.set_footer(text="CapitanCoditos, Tu afk favorito. • Haz clic en una partida para ver el análisis detallado.")
    
    return embed

# Discord utility functions
async def create_match_analysis_embed(riot_id: str, participant, match_data, game_duration, analysis_message: str, summoner_profile=None):
    """Create a standardized Discord embed for match analysis"""
    game_name = parse_riot_id(riot_id)[0]
    
    champ = participant["championName"]
    kda = format_kda(participant)
    resultado, _ = get_match_result_info(participant)
    game_mode = match_data["info"]["gameMode"] or "Desconocido"
    
    # Create champion icon URL
    champion_icon_url = get_champion_icon_url(champ)

    # Custom mapping for game mode names
    custom_game_modes = {
        "CLASSIC": "Grieta del Invocador",
        "ARAM": "ARAM",
        "URF": "Ultra Rapid Fire", 
        "CHERRY": "Arena de Noxus",
        "ULTBOOK": "Libro de Hechizos",
        "DESCONOCIDO": "Desconocido"
    }
    game_mode_name = custom_game_modes.get(game_mode, game_mode)

    # Create Discord embed
    embed = discord.Embed(
        title=f"Última partida de {riot_id}",
        description=f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {game_duration} minutos",
        color=0x00ff00 if resultado == "Victoria" else 0xff0000
    )
    embed.add_field(
        name=f"Campeón: {champ}",
        value=f"Modo de juego: {game_mode_name}",
        inline=False
    )
      # Truncate analysis message if too long
    if len(analysis_message) > 1020:  # Leave margin for formatting
        analysis_message = analysis_message[:1017] + "..."
    
    embed.add_field(
        name="Análisis de la partida:",
        value=analysis_message,
        inline=False
    )
    
    embed.set_thumbnail(url=champion_icon_url)
    
    # Set summoner profile icon if available
    if summoner_profile:
        profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
        embed.set_author(name=f"Nivel {summoner_profile['summonerLevel']}", icon_url=profile_icon_url)
    
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    
    return embed

async def create_simple_match_embed(riot_id: str, participant, match_data, game_duration, summoner_profile=None):
    """Create a simple Discord embed for remake/very short matches without AI analysis"""
    game_name = parse_riot_id(riot_id)[0]
    
    champ = participant["championName"]
    kda = format_kda(participant)
    resultado, _ = get_match_result_info(participant)
    game_mode = match_data["info"]["gameMode"] or "Desconocido"
    
    # Create champion icon URL
    champion_icon_url = get_champion_icon_url(champ)

    # Custom mapping for game mode names
    custom_game_modes = {
        "CLASSIC": "Grieta del Invocador",
        "ARAM": "ARAM",
        "URF": "Ultra Rapid Fire", 
        "CHERRY": "Arena de Noxus"
    }
    game_mode_name = custom_game_modes.get(game_mode, game_mode)

    # Create Discord embed
    embed = discord.Embed(
        title=f"Última partida de {riot_id}",
        description=f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {game_duration} minutos",
        color=0x00ff00 if resultado == "Victoria" else 0xff0000
    )
    embed.add_field(
        name=f"Campeón: {champ}",
        value=f"Modo de juego: {game_mode_name}",
        inline=False
    )
    
    # Check if it's a very short game (likely remake)
    if game_duration < 5:
        analysis_message = "⚠️ **Partida muy corta** - Esta partida fue muy breve (posible remake). No hay suficientes datos para un análisis completo."
    elif game_duration < 8:
        analysis_message = "⏰ **Partida corta** - Esta partida terminó muy rápido. El análisis puede no ser representativo del rendimiento habitual."
    else:
        analysis_message = "📊 **Partida sin análisis** - No se generó análisis automático para esta partida."
    
    embed.add_field(
        name="Estado de la partida:",
        value=analysis_message,
        inline=False
    )
    
    embed.set_thumbnail(url=champion_icon_url)
    
    # Set summoner profile icon if available
    if summoner_profile:
        profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
        embed.set_author(name=f"Nivel {summoner_profile['summonerLevel']}", icon_url=profile_icon_url)
    
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    
    return embed

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

def is_valid_match_for_analysis(match_data, participant):
    """Check if a match is valid for AI analysis (not a remake or very short game)."""
    game_duration_seconds = match_data["info"]["gameDuration"]
    game_duration_minutes = game_duration_seconds // 60
    
    # Check for remake conditions
    # 1. Very short games (less than 5 minutes are usually remakes)
    if game_duration_minutes < 5:
        return False
    
    # 2. Check if game ended in early surrender (remake)
    game_ended_early = match_data["info"].get("gameEndedInEarlySurrender", False)
    if game_ended_early:
        return False
    
    # 3. Check for extremely low stats that suggest a remake
    # In remakes, players usually have very low kills, deaths, and damage
    total_damage = participant.get("totalDamageDealtToChampions", 0)
    kills = participant.get("kills", 0)
    deaths = participant.get("deaths", 0)
    assists = participant.get("assists", 0)
    
    # If all stats are extremely low, it's likely a remake
    if (total_damage < 500 and kills == 0 and deaths <= 1 and assists == 0 and 
        game_duration_minutes < 8):
        return False
    
    return True
