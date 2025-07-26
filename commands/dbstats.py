import discord
from discord import app_commands
from database import get_summoner_stats
from utils.helpers import handle_command_error

async def db_stats(interaction: discord.Interaction):
    """Show database statistics"""
    await interaction.response.defer()

    try:
        stats = get_summoner_stats()
        
        embed = discord.Embed(
            title="📊 Estadísticas de la Base de Datos",
            color=0x0099ff
        )
        
        embed.add_field(
            name="👥 Invocadores Guardados", 
            value=f"**{stats['total_summoners']}** únicos",
            inline=True
        )
        
        embed.add_field(
            name="🔍 Búsquedas Totales", 
            value=f"**{stats['total_searches']}** realizadas",
            inline=True
        )
        
        if stats['total_summoners'] > 0:
            avg_searches = stats['total_searches'] / stats['total_summoners']
            embed.add_field(
                name="📈 Promedio de Búsquedas", 
                value=f"**{avg_searches:.1f}** por invocador",
                inline=True
            )
        
        embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await handle_command_error(interaction, e)

def register_dbstats(tree):
    @tree.command(name="dbstats", description="Muestra estadísticas de la base de datos de invocadores.")
    async def command(interaction: discord.Interaction):
        await db_stats(interaction)
