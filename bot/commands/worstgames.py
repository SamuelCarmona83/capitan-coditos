import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import build_worst_games_embed, handle_command_error

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]

ROLE_CHOICES = [
    app_commands.Choice(name="Todos los roles", value="ALL"),
    app_commands.Choice(name="Top", value="TOP"),
    app_commands.Choice(name="Jungla", value="JUNGLE"),
    app_commands.Choice(name="Mid", value="MIDDLE"),
    app_commands.Choice(name="Bot (ADC)", value="BOTTOM"),
    app_commands.Choice(name="Support", value="UTILITY"),
]


async def worstgames(interaction: discord.Interaction, riot_id: str, partidas: int = 20, region: str = "LAN", rol: str = "ALL"):
    await interaction.response.defer()
    try:
        estimated_min = max(1, int((partidas * 1.3) / 60))
        progress_msg = await interaction.followup.send(
            f"🔍 Analizando peores partidas de **{riot_id}** ({region}) — últimas **{partidas}** partidas ranked...\n"
            f"⏳ Tiempo estimado: **~{estimated_min} {'minuto' if estimated_min == 1 else 'minutos'}**.",
            wait=True,
        )

        # Start the Celery task
        task_resp = await api_client.post("/api/tasks/worst-games", json={
            "riot_id": riot_id, "count": partidas, "region": region, "role": rol,
        })
        task_id = task_resp["task_id"]

        # Poll for progress / result
        async def on_progress(current: int, total: int):
            pct = int((current / total) * 100) if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await progress_msg.edit(
                    content=(
                        f"🔍 Analizando peores partidas de **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        result = await api_client.poll_task(task_id, progress_callback=on_progress)
        embed = build_worst_games_embed(result)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_command_error(interaction, e)


def register_worstgames(tree):
    @app_commands.describe(
        riot_id="Riot ID (ej: Roga#LAN)",
        partidas="Número de partidas a analizar",
        region="Región",
        rol="Filtrar por rol",
    )
    @app_commands.choices(region=REGION_CHOICES, rol=ROLE_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="worstgames", description="Muestra tus peores partidas ranked con análisis de rendimiento 📉")
    async def command(
        interaction: discord.Interaction,
        riot_id: str,
        partidas: int = 20,
        region: str = "LAN",
        rol: str = "ALL",
    ):
        await worstgames(interaction, riot_id, partidas, region, rol)
