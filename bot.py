import discord
from discord import app_commands
import os
from commands import register_commands

# Constants
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Discord setup
intents = discord.Intents.default()
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

client.run(DISCORD_TOKEN)
