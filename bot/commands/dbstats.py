import discord
from discord import app_commands

from utils import api_client
from utils.embed_builders import build_db_stats_embed, handle_command_error


async def dbstats(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        stats = await api_client.get("/api/db/stats")
        embed = build_db_stats_embed(stats)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_dbstats(tree):
    @tree.command(name="dbstats", description="Estadísticas de la base de datos y caché 📊")
    async def command(interaction: discord.Interaction):
        await dbstats(interaction)
