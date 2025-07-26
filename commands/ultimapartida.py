import discord
from discord import app_commands
from utils.helpers import create_ultima_partida_embed, handle_command_error
from utils.autocomplete import riot_id_autocomplete
from database import save_summoner

async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(riot_id)
        
        embed = await create_ultima_partida_embed(riot_id)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_ultimapartida(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str):
        await ultimapartida(interaction, riot_id)
