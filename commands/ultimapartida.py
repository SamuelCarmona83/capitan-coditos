import discord
from discord import app_commands
from utils.helpers import create_ultima_partida_embed, handle_command_error

async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        embed = await create_ultima_partida_embed(riot_id)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_ultimapartida(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str):
        await ultimapartida(interaction, riot_id)
