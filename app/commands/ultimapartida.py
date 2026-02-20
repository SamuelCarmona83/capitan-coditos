import discord
from discord import app_commands
from utils.helpers import create_ultima_partida_embed, handle_command_error
from utils.autocomplete import riot_id_autocomplete
from database import save_summoner
from riot.api import REGION_MAP

REGION_CHOICES = [
    app_commands.Choice(name=region, value=region)
    for region in REGION_MAP.keys()
]

async def ultimapartida(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(riot_id)
        
        embed = await create_ultima_partida_embed(riot_id, region=region)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_ultimapartida(tree):
    @app_commands.describe(
        riot_id="Tu Riot ID completo (ej: Roga#LAN)",
        region="Región del servidor (default: LAN)"
    )
    @app_commands.choices(region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
        await ultimapartida(interaction, riot_id, region)
