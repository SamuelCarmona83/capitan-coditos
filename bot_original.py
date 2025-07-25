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


async def send_long_message(interaction, content):
    # Divide el mensaje en partes si excede el límite de Discord (2000 caracteres)
    max_length = 2000
    for i in range(0, len(content), max_length):
        await interaction.followup.send(content[i:i + max_length])


@app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
@tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    if "#" not in riot_id:
        await interaction.followup.send("❌ El Riot ID debe tener formato `Nombre#Tag` (ej: Roga#LAN)")
        return

    game_name, tag_line = riot_id.split("#")

    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        await interaction.followup.send("⚠️ No encontré ese Riot ID.")
        return

    account_data = r.json()
    puuid = account_data["puuid"]

    matches = get_match_history(puuid)
    if not matches:
        await interaction.followup.send("⚠️ No encontré partidas recientes.")
        return

    match_data = get_match_data(matches[0])
    participant = next(p for p in match_data["info"]["participants"] if p["puuid"] == puuid)

    champ = participant["championName"]
    kda = f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"
    resultado = "Victoria" if participant["win"] else "Derrota"
    tiempo = match_data["info"]["gameDuration"] // 60

    mensaje_openai = await generar_mensaje_openai(game_name, {
        "kills": participant["kills"],
        "deaths": participant["deaths"],
        "assists": participant["assists"],
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "gameDuration": tiempo
    })

    full_message = (
        f"**{riot_id}** jugó como **{champ}**\n"
        f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {tiempo} minutos\n\n"
        f"{mensaje_openai}"
    )

    await send_long_message(interaction, full_message)


def encontrar_peor_jugador(participants):
    def calcular_score(p):
        k = p["kills"]
        d = p["deaths"]
        a = p["assists"]
        damage = p["totalDamageDealtToChampions"]
        return (k + a) / max(1, d) + (damage / 10000)

    scores = {}
    for p in participants:
        # Try different name fields - riotIdGameName is more reliable
        name = p.get('riotIdGameName') or p.get('summonerName') or f"Player_{p.get('participantId', 'Unknown')}"
        if name:
            scores[name] = calcular_score(p)
    
    if not scores:  # If no valid players found
        return "Unknown", participants[0], 0
        
    peor_nombre = min(scores, key=scores.get)
    peor_partida = next(p for p in participants if 
                       (p.get('riotIdGameName') or p.get('summonerName') or f"Player_{p.get('participantId', 'Unknown')}") == peor_nombre)
    return peor_nombre, peor_partida, scores[peor_nombre]


# Fetch summoner data by name
def get_summoner_data(game_name, tag_line):


    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        raise ValueError("Summoner not found.")
    elif response.status_code == 429:
        raise ValueError("Rate limit exceeded. Please try again later.")
    response.raise_for_status()
    return response.json()


# Fetch match history by PUUID
def get_match_history(puuid):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 429:
        raise ValueError("Rate limit exceeded. Please try again later.")
    response.raise_for_status()
    return response.json()


# Fetch match data by match ID
def get_match_data(match_id):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 429:
        raise ValueError("Rate limit exceeded. Please try again later.")
    response.raise_for_status()
    return response.json()


@app_commands.describe(invocador="Tu nombre de invocador (ej: Roga#LAN)")
@tree.command(name="analizarpartida", description="Analiza tu última partida y encuentra al peor jugador con un resumen divertido.")
async def analizar_partida(interaction: discord.Interaction, invocador: str):
    await interaction.response.defer()

    try:
        if "#" in invocador:
            game_name, tag_line = invocador.split("#")

        # Fetch summoner data
        summoner = get_summoner_data(game_name, tag_line)
        puuid = summoner['puuid']

        # Fetch match history
        matches = get_match_history(puuid)
        if not matches:
            await interaction.followup.send("⚠️ No se encontraron partidas recientes.")
            return        # Fetch match data
        match_data = get_match_data(matches[0])
        participants = match_data['info']['participants']
        game_duration = match_data['info']['gameDuration'] // 60  # Convert to minutes        # Find the player's team
        player = next(p for p in participants if p['puuid'] == puuid)
        player_team = player['teamId']
        
        # Get allies (same team as the player)
        aliados = [p for p in participants if p['teamId'] == player_team]
        
        # Analyze the worst player from the ally team only
        peor_nombre, peor_stats, _ = encontrar_peor_jugador(aliados)
        peor_stats['gameDuration'] = game_duration  # Add game duration to stats
        mensaje = await generar_mensaje_openai(peor_nombre, peor_stats)        
        
        # Format team stats with consistent styling - use riotIdGameName if summonerName is empty
        resumen_equipo = "\n".join([
            f"• **{p.get('riotIdGameName', p.get('summonerName', 'Unknown'))}** - {p['championName']} (`{p['kills']}/{p['deaths']}/{p['assists']}`)"
            for p in aliados
        ])

        resultado = "Victoria" if player["win"] else "Derrota"
        emoji_resultado = "🏆" if player["win"] else "💔"

        # Create formatted message
        mensaje_formateado = (
            f"{emoji_resultado} **{resultado}** - ⏱️ {game_duration} min\n"
            f"**Equipo de {invocador}:**\n"
            f"{resumen_equipo}\n"
            f"\n{mensaje}"
        )

        await interaction.followup.send(mensaje_formateado)

    except ValueError as e:
        await interaction.followup.send(f"⚠️ {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Ocurrió un error: {str(e)}")


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