import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import (
    build_match_history_embed,
    build_match_detail_embed,
    handle_command_error,
)

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]


class MatchHistoryView(discord.ui.View):
    """One button per recent match. Clicking fetches AI analysis for that match."""

    def __init__(self, riot_id: str, matches: list, region: str = "LAN"):
        super().__init__(timeout=300)
        self.riot_id = riot_id
        self.matches = matches
        self.region = region

        for i, m in enumerate(matches[:10]):
            p = m["participant"]
            emoji = "🏆" if p["win"] else "💔"
            btn = discord.ui.Button(
                label=f"{emoji} {p['championName']} ({i+1})",
                style=discord.ButtonStyle.success if p["win"] else discord.ButtonStyle.danger,
                custom_id=f"match_{i}",
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def cb(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                m = self.matches[idx]
                analysis = None
                if m.get("valid_for_analysis"):
                    ai = await api_client.post("/api/ai/match-analysis", json={
                        "nombre": self.riot_id.split("#")[0],
                        "stats": m["stats"],
                        "participant": m["participant"],
                        "game_mode": m["game_mode"],
                    })
                    analysis = ai.get("analysis")
                embed = build_match_detail_embed(self.riot_id, m, idx + 1, analysis)
                await interaction.followup.send(embed=embed)
            except Exception as e:
                await handle_command_error(interaction, e)
        return cb


async def historial_partidas(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
    await interaction.response.defer()
    try:
        data = await api_client.get(
            f"/api/summoner/{riot_id}/match-history",
            params={"region": region, "count": 10},
        )
        embed = build_match_history_embed(data)
        view = MatchHistoryView(riot_id, data.get("matches", []), region)
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_historialpartidas(tree):
    @app_commands.describe(riot_id="Riot ID (ej: Roga#LAN)", region="Región (default: LAN)")
    @app_commands.choices(region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="historialpartidas", description="Historial de las últimas 10 partidas 📋")
    async def command(interaction: discord.Interaction, riot_id: str, region: str = "LAN"):
        await historial_partidas(interaction, riot_id, region)
