import discord
import requests
import os

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
REGION = 'la2'  # Cambia a la tuya: na1, la1, la2, br1, etc.

intents = discord.Intents.default()
client = discord.Client(intents=intents)

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

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('/ultimapartida'):
        summoner_name = message.content.split(' ')[1]
        summoner = get_summoner_data(summoner_name)
        puuid = summoner['puuid']
        matches = get_match_history(puuid)
        match_data = get_match_data(matches[0])

        # Encuentra al jugador en la partida
        participant_data = next(p for p in match_data['info']['participants'] if p['puuid'] == puuid)

        champ = participant_data['championName']
        kills = participant_data['kills']
        deaths = participant_data['deaths']
        assists = participant_data['assists']
        win = participant_data['win']
        duration = match_data['info']['gameDuration'] // 60

        resultado = "Victoria" if win else "Derrota"
        msg = f"**{summoner_name}** jugó como **{champ}** - {resultado}\nKDA: {kills}/{deaths}/{assists} en {duration} min."
        await message.channel.send(msg)

@client.event
async def on_ready():
    print(f'Bot listo como {client.user}')

client.run(DISCORD_TOKEN)
