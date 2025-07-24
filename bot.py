import discord
from discord import app_commands
import requests
import asyncio
import os
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
REGION = "la2"  # LAS
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


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


# Slash command: un solo argumento como RiotID
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

    await interaction.followup.send(
        f"**{riot_id}** jugó como **{champ}**\n"
        f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {tiempo} minutos"
    )


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot conectado como {client.user}")


client.run(DISCORD_TOKEN)
