import discord
from discord import app_commands
import requests
import os
from openai import AsyncOpenAI

# Constants
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Discord setup
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# Utility functions
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


# Riot API functions
def get_summoner_data(game_name, tag_line):
    """Fetch summoner data by Riot ID."""
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return make_riot_request(url)


def get_match_history(puuid):
    """Fetch match history by PUUID."""
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
    return make_riot_request(url)


def get_match_data(match_id):
    """Fetch match data by match ID."""
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return make_riot_request(url)


async def get_player_match_data(riot_id):
    """Get player's latest match data. Returns (participant, match_data, game_duration)."""
    try:
        game_name, tag_line = parse_riot_id(riot_id)
        summoner = get_summoner_data(game_name, tag_line)
        puuid = summoner['puuid']
        
        matches = get_match_history(puuid)
        if not matches:
            raise ValueError("No se encontraron partidas recientes.")
        
        match_data = get_match_data(matches[0])
        participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)
        game_duration = match_data["info"]["gameDuration"] // 60
        
        return participant, match_data, game_duration
    except requests.exceptions.RequestException:
        raise ValueError("Error al conectar con la API de Riot.")


# OpenAI integration
async def generar_mensaje_openai(nombre, stats):
    """Generate sarcastic LoL coach message using OpenAI."""
    prompt = f"""
    Actúa como un entrenador de League of Legends brutalmente honesto y sarcástico.
    Genera un mensaje corto y directo usando el formato de texto de Discord:
    - Usa **negrita** para énfasis
    - Usa *cursiva* para términos de juego
    - Usa __subrayado__ para nombres
    - Usa ~~tachado~~ para errores o fallos
    - Usa `código` para números o estadísticas
    
    Estadísticas del jugador:
    Invocador: __**{nombre}**__
    KDA: `{stats['kills']}/{stats['deaths']}/{stats['assists']}`
    Daño: `{stats['totalDamageDealtToChampions']:,}`
    Tiempo: `{stats['gameDuration']} min`

    Escribe un mensaje breve (máximo 2 oraciones) con humor negro gamer, mencionando específicamente sus estadísticas.
    Usa memes de gaming, referencias a otros juegos más fáciles (Candy Crush, Minecraft, etc), o tiempo en pantalla gris.
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un jugador de LoL con humor ácido, opiniones fuertes y objetividad si el desempeño fue bueno."},
            {"role": "user", "content": prompt + "\n\nSi el jugador realizó una buena actuación, evalúa objetivamente su desempeño."}
        ],
        temperature=0.8
    )

    return response.choices[0].message.content.strip()


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


# Discord commands
@app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
@tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        participant, _, game_duration = await get_player_match_data(riot_id)
        game_name = parse_riot_id(riot_id)[0]
        
        champ = participant["championName"]
        kda = format_kda(participant)
        resultado, _ = get_match_result_info(participant)
        
        stats = create_stats_dict(participant, game_duration)
        mensaje_openai = await generar_mensaje_openai(game_name, stats)

        full_message = (
            f"**{riot_id}** jugó como **{champ}**\n"
            f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {game_duration} minutos\n\n"
            f"{mensaje_openai}"
        )

        await send_long_message(interaction, full_message)
    except Exception as e:
        await handle_command_error(interaction, e)


@app_commands.describe(invocador="Tu nombre de invocador (ej: Roga#LAN)")
@tree.command(name="analizarpartida", description="Analiza tu última partida y encuentra al peor jugador con un resumen divertido.")
async def analizar_partida(interaction: discord.Interaction, invocador: str):
    await interaction.response.defer()

    try:
        participant, match_data, game_duration = await get_player_match_data(invocador)
        participants = match_data['info']['participants']
        
        # Get allies (same team as the player)
        player_team = participant['teamId']
        aliados = [p for p in participants if p['teamId'] == player_team]
        
        # Analyze the worst player from the ally team
        peor_nombre, peor_stats, _ = encontrar_peor_jugador(aliados)
        stats = create_stats_dict(peor_stats, game_duration)
        mensaje = await generar_mensaje_openai(peor_nombre, stats)
        
        # Format team stats
        resumen_equipo = "\n".join([
            f"• **{get_player_name(p)}** - {p['championName']} (`{format_kda(p)}`)"
            for p in aliados
        ])

        resultado, emoji_resultado = get_match_result_info(participant)

        # Create formatted message
        mensaje_formateado = (
            f"{emoji_resultado} **{resultado}** - ⏱️ {game_duration} min\n"
            f"**Equipo de {invocador}:**\n"
            f"{resumen_equipo}\n"
            f"\n{mensaje}"
        )

        await interaction.followup.send(mensaje_formateado)
    except Exception as e:
        await handle_command_error(interaction, e)


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot conectado como {client.user}")

    cmds = await tree.fetch_commands()
    print("🔍 Comandos registrados:")
    for cmd in cmds:
        print(f"- {cmd.name}")
    print("\n🌐 Comandos sincronizados correctamente.")


client.run(DISCORD_TOKEN)
