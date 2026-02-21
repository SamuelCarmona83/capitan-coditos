import discord
from discord import app_commands

from utils import api_client
from utils.autocomplete import riot_id_autocomplete
from utils.embed_builders import handle_command_error

REGION_CHOICES = [
    app_commands.Choice(name=r, value=r)
    for r in ["LAN","LAS","NA","BR","EUW","EUNE","TR","RU","KR","JP","OCE","PH","SG","TH","TW","VN"]
]

PARTIDAS_CHOICES = [
    app_commands.Choice(name="25 partidas",  value=25),
    app_commands.Choice(name="50 partidas",  value=50),
    app_commands.Choice(name="100 partidas", value=100),
    app_commands.Choice(name="250 partidas", value=250),
]

BUCKET_EMOJIS = ["🟢", "🟡", "🟠", "🔴", "⚫"]


def _bar(pct: float, width: int = 12) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _build_duration_embed(result: dict) -> discord.Embed:
    if result.get("error"):
        return discord.Embed(
            title="❌ No se pudo completar el análisis",
            description=result["error"],
            color=0xFF4444,
        )

    riot_id = result["riot_id"]
    buckets = result.get("buckets", [])
    stats = result.get("general_stats", {})
    summoner_profile = result.get("summoner_profile")

    embed = discord.Embed(
        title=f"⏱️ Distribución de duración de partidas — {riot_id}",
        description=(
            f"📊 **{stats.get('total_analyzed', 0)}** partidas analizadas "
            f"(de {stats.get('total_fetched', 0)} obtenidas"
            + (f", {stats.get('skipped_remakes', 0)} remakes descartados" if stats.get("skipped_remakes") else "")
            + f") | **{stats.get('win_rate', 0):.1f}%** WR general\n"
            f"🕒 Duración promedio: **{stats.get('avg_duration_min', 0):.1f} min**"
        ),
        color=0x00B4D8,
    )

    lines = []
    for i, bucket in enumerate(buckets):
        if bucket.get("total", 0) == 0:
            continue
        emoji  = BUCKET_EMOJIS[i] if i < len(BUCKET_EMOJIS) else "⚪"
        bar    = _bar(bucket["pct"])
        wins   = bucket["wins"]
        losses = bucket["losses"]
        total  = bucket["total"]
        win_bar  = "🟩" * round(wins  / total * 8)
        loss_bar = "🟥" * round(losses / total * 8)
        lines.append(
            f"{emoji} **{bucket['label']}** — `{bar}` **{bucket['pct']:.1f}%** ({total} partidas)\n"
            f"   {win_bar}{loss_bar}  ✅ {wins}V / ❌ {losses}D  "
            f"({bucket['win_pct']:.0f}% WR en este tramo)"
        )

    embed.add_field(
        name="📈 Distribución por duración:",
        value="\n".join(lines) if lines else "Sin datos",
        inline=False,
    )

    # Cumulative summary
    n = stats.get("total_analyzed", 0)
    if n:
        cum_lines = []
        running = 0
        for i, bucket in enumerate(buckets[:-1]):
            running += bucket["total"]
            cum_wins = sum(b["wins"] for b in buckets[:i+1])
            cum_pct  = running / n * 100
            cum_wr   = cum_wins / running * 100 if running else 0
            cum_lines.append(
                f"Antes de **{bucket['max']} min**: `{cum_pct:.1f}%` de partidas "
                f"({running}/{n}) — {cum_wr:.0f}% WR"
            )
        if cum_lines:
            embed.add_field(name="📉 Acumulados:", value="\n".join(cum_lines), inline=False)

    if summoner_profile:
        from utils.embed_builders import _icon_url
        icon_url = _icon_url(summoner_profile.get("profileIconId", 0))
        embed.set_author(
            name=f"Nivel {summoner_profile.get('summonerLevel', '?')}",
            icon_url=icon_url,
        )

    embed.set_footer(text="CapitanCoditos • Remakes (<5 min) excluidos del análisis")
    return embed


async def duracionpartidas(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
    await interaction.response.defer()
    try:
        estimated_min = max(1, int((partidas * 1.2) / 60))
        progress_msg = await interaction.followup.send(
            f"⏱️ Analizando duración de las últimas **{partidas}** partidas de **{riot_id}** ({region})...\n"
            f"⏳ Tiempo estimado: **~{estimated_min} {'minuto' if estimated_min == 1 else 'minutos'}**.",
            wait=True,
        )

        task_resp = await api_client.post("/api/tasks/duration-stats", json={
            "riot_id": riot_id, "count": partidas, "region": region,
        })
        task_id = task_resp["task_id"]

        async def on_progress(current: int, total: int):
            pct = int((current / total) * 100) if total else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await progress_msg.edit(
                    content=(
                        f"⏱️ Analizando **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        result = await api_client.poll_task(task_id, progress_callback=on_progress)
        embed = _build_duration_embed(result)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_command_error(interaction, e)


def register_duracionpartidas(tree):
    @app_commands.describe(
        riot_id="Tu Riot ID completo (ej: Roga#LAN)",
        partidas="Número de partidas a analizar",
        region="Región del servidor",
    )
    @app_commands.choices(partidas=PARTIDAS_CHOICES, region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(
        name="duracionpartidas",
        description="Muestra qué % de tus partidas terminan antes del min 15, 20, 25 y 30 ⏱️",
    )
    async def command(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
        await duracionpartidas(interaction, riot_id, partidas, region)
