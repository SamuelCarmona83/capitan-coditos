import discord
from discord import app_commands
import os
from commands import register_commands
from riot.active_game_notify import notify_active_games_task
import asyncio

# Constants
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Discord setup
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True  # Necesario para enviar mensajes
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    register_commands(tree)
    await tree.sync()
    print(f"✅ Bot conectado como {client.user}")

    cmds = await tree.fetch_commands()
    print("🔍 Comandos registrados:")
    for cmd in cmds:
        print(f"- {cmd.name}")
    print("\n🌐 Comandos sincronizados correctamente.")

    # Inicia la tarea de notificación de amigos en partida (ajusta el channel_id)
    channel_id = int(os.getenv("NOTIFY_CHANNEL_ID", 1163478665917644903))
    if channel_id:
        asyncio.create_task(notify_active_games_task(client, channel_id))
    else:
        print("[ActiveGameNotify] NOTIFY_CHANNEL_ID no configurado.")

client.run(DISCORD_TOKEN)
