import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import build_last_match_embed, handle_command_error

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]


async def ultimapartida(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
    await interaction.response.defer()
    try:
        data = await api_client.get(f"/api/summoner/{riot_id}/last-match", params={"region": region})
        embed = build_last_match_embed(data)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_ultimapartida(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)", region="Región (default: LAN)")
    @app_commands.choices(region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
        await ultimapartida(interaction, riot_id, region)
