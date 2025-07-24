import discord
from discord import app_commands
import requests
import asyncio
import os
from riotwatcher import LolWatcher
from openai import AsyncOpenAI

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
REGION = "la2"
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

lol_watcher = LolWatcher(RIOT_API_KEY)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def get_summoner_data(summoner_name):
    url = f"https://{REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = requests.get(url, headers=headers)
    return r.json()


def get_match_history(puuid):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = requests.get(url, headers=headers)
    return r.json()


def get_match_data(match_id):
    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    r = requests.get(url, headers=headers)
    return r.json()


async def generar_mensaje_openai(nombre, stats):
    prompt = f"""
    Actúa como un entrenador de League of Legends brutalmente honesto y sarcástico.
    Tienes acceso a las estadísticas de una partida reciente. Identifica al jugador con el peor desempeño.
    Diles veganos. que pasaron tiempo en pantalla gris. o que deberían haber jugado al Candy Crush.
    Estadísticas:
    - Jugador: {nombre}
    - KDA: {stats['kills']}/{stats['deaths']}/{stats['assists']}
    - Daño: {stats['totalDamageDealtToChampions']}
    - Tiempo: {stats['gameDuration']} minutos

    Escribe un mensaje breve (máximo 2 oraciones) con humor negro gamer.
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un jugador de LoL con humor ácido y opiniones fuertes."},
            {"role": "user", "content": prompt}
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

    scores = {p["summonerName"]: calcular_score(p) for p in participants}
    peor_nombre = min(scores, key=scores.get)
    peor_partida = next(p for p in participants if p["summonerName"] == peor_nombre)
    return peor_nombre, peor_partida, scores[peor_nombre]


@app_commands.describe(invocador="Tu nombre de invocador (ej: Roga#LAN)")
@tree.command(name="analizarpartida", description="Analiza tu última partida y encuentra al peor jugador con un resumen divertido.")
async def analizar_partida(interaction: discord.Interaction, invocador: str):
    await interaction.response.defer()

    try:
        if "#" in invocador:
            invocador = invocador.split("#")[0]

        summoner = lol_watcher.summoner.by_name(REGION, invocador)
        puuid = summoner['puuid']

        matches = lol_watcher.match.matchlist_by_puuid("americas", puuid, count=1)
        if not matches:
            await interaction.followup.send("⚠️ No se encontraron partidas recientes.")
            return

        match_data = lol_watcher.match.by_id("americas", matches[0])
        participants = match_data['info']['participants']

        peor_nombre, peor_stats, _ = encontrar_peor_jugador(participants)
        mensaje = await generar_mensaje_openai(peor_nombre, peor_stats)

        aliados = [p for p in participants if p['teamId'] == peor_stats['teamId']]
        resumen_equipo = "\n".join([
            f"**{p['summonerName']}** - {p['championName']} - {p['kills']}/{p['deaths']}/{p['assists']}"
            for p in aliados
        ])

        await interaction.followup.send(f"**Resumen del equipo de {invocador}:**\n{resumen_equipo}\n\n{mensaje}")

    except Exception as e:
        await interaction.followup.send(f"❌ Ocurrió un error: {str(e)}")


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot conectado como {client.user}")


client.run(DISCORD_TOKEN)