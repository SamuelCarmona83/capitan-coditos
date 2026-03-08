import asyncio
import os

import discord
from discord import app_commands

from commands import register_commands
from riot.active_game_notify import notify_active_games_task

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

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
        print(f"  - {cmd.name}")

    channel_id = os.getenv("NOTIFY_CHANNEL_ID")
    user_id = os.getenv("NOTIFY_USER_ID")

    if channel_id:
        asyncio.create_task(notify_active_games_task(bot=client, channel_id=int(channel_id)))
    if user_id:
        asyncio.create_task(notify_active_games_task(bot=client, user_id=int(user_id)))
    if not channel_id and not user_id:
        print("⚠️  NOTIFY_CHANNEL_ID / NOTIFY_USER_ID not set. Active-game notifications disabled.")


client.run(DISCORD_TOKEN)
