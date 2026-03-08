import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import (
    build_team_analysis_embed,
    build_last_match_embed,
    handle_command_error,
)

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]


class TeamMemberView(discord.ui.View):
    """Buttons to view the last match of each ally."""

    def __init__(self, allies: list):
        super().__init__(timeout=300)
        for i, p in enumerate(allies[:5]):
            name = p.get("riotIdGameName") or p.get("summonerName") or f"Player_{i+1}"
            tag = p.get("riotIdTagline")
            riot_id = f"{name}#{tag}" if tag else None

            btn = discord.ui.Button(
                label=f"{name} ({p['championName']})",
                style=discord.ButtonStyle.secondary,
                custom_id=f"ally_{i}",
                disabled=(riot_id is None),
            )
            if riot_id:
                btn.callback = self._make_callback(riot_id)
            else:
                btn.callback = self._make_disabled_callback(name)
            self.add_item(btn)

    def _make_callback(self, riot_id: str):
        async def cb(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                data = await api_client.get(f"/api/summoner/{riot_id}/last-match")
                embed = build_last_match_embed(data)
                await interaction.followup.send(embed=embed)
            except Exception as e:
                await handle_command_error(interaction, e)
        return cb

    def _make_disabled_callback(self, name: str):
        async def cb(interaction: discord.Interaction):
            await interaction.response.send_message(
                f"❌ No se puede obtener info de {name} (Riot ID no disponible)", ephemeral=True
            )
        return cb


async def analizar_partida(interaction: discord.Interaction, invocador: str, region: str = "LAN"):
    await interaction.response.defer()
    try:
        data = await api_client.get(f"/api/summoner/{invocador}/team-analysis", params={"region": region})
        embed = build_team_analysis_embed(data)
        allies = data.get("allies", [])
        view = TeamMemberView(allies) if data.get("valid_for_analysis") else None
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_analizarpartida(tree):
    @app_commands.describe(invocador="Riot ID (ej: Roga#LAN)", region="Región (default: LAN)")
    @app_commands.choices(region=REGION_CHOICES)
    @app_commands.autocomplete(invocador=riot_id_autocomplete)
    @tree.command(name="analizarpartida", description="Analiza el equipo de tu última partida 🔍")
    async def command(interaction: discord.Interaction, invocador: str, region: str = "LAN"):
        await analizar_partida(interaction, invocador, region)
