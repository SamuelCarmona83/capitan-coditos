import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import build_matchups_embed, handle_command_error

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]


async def matchups(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
    await interaction.response.defer()
    try:
        estimated_min = int((partidas * 1.3) / 60)
        progress_msg = await interaction.followup.send(
            f"🔍 Analizando matchups de **{riot_id}** ({region}) — últimas **{partidas}** partidas ranked...\n"
            f"⏳ Tiempo estimado: **~{estimated_min} minutos**.",
            wait=True,
        )

        # Start the Celery task
        task_resp = await api_client.post("/api/tasks/matchups", json={
            "riot_id": riot_id, "count": partidas, "region": region,
        })
        task_id = task_resp["task_id"]

        # Poll for progress / result
        async def on_progress(current: int, total: int):
            pct = int((current / total) * 100) if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await progress_msg.edit(
                    content=(
                        f"🔍 Analizando matchups de **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        result = await api_client.poll_task(task_id, progress_callback=on_progress)
        embed = build_matchups_embed(result)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_command_error(interaction, e)


def register_matchups(tree):
    @app_commands.describe(riot_id="Riot ID (ej: Roga#LAN)", partidas="Partidas a analizar", region="Región")
    @app_commands.choices(region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="matchups", description="Analiza tus matchups más difíciles en ranked 🎯")
    async def command(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
        await matchups(interaction, riot_id, partidas, region)
