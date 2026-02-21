import discord
from discord import app_commands
from riot.api import get_game_duration_stats, REGION_MAP
from utils.helpers import parse_riot_id, get_summoner_icon_url, handle_command_error
from utils.autocomplete import riot_id_autocomplete
from database import save_summoner

REGION_CHOICES = [
    app_commands.Choice(name=region, value=region)
    for region in REGION_MAP.keys()
]

PARTIDAS_CHOICES = [
    app_commands.Choice(name="25 partidas",  value=25),
    app_commands.Choice(name="50 partidas",  value=50),
    app_commands.Choice(name="100 partidas", value=100),
    app_commands.Choice(name="250 partidas", value=250),
]

# Emojis for each bucket – colour gradient from green (short) to red (long)
BUCKET_EMOJIS = ["🟢", "🟡", "🟠", "🔴", "⚫"]

def _bar(pct: float, width: int = 12) -> str:
    """Build a simple block progress-bar string."""
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


async def duracion_partidas(
    interaction: discord.Interaction,
    riot_id: str,
    partidas: int = 50,
    region: str = "LAN",
):
    await interaction.response.defer()

    try:
        save_summoner(riot_id, region=region)

        estimated_time = max(1, int((partidas * 1.2) / 60))
        progress_msg = await interaction.followup.send(
            f"⏱️ Analizando duración de las últimas **{partidas}** partidas de **{riot_id}** ({region})...\n"
            f"⏳ Tiempo estimado: **~{estimated_time} minutos**.",
            wait=True,
        )

        async def progress_callback(current, total):
            try:
                pct = int((current / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await progress_msg.edit(
                    content=(
                        f"⏱️ Analizando **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** partidas [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        buckets, stats, summoner_profile = await get_game_duration_stats(
            riot_id,
            count=partidas,
            progress_callback=progress_callback,
            region=region,
        )

        # ── Build embed ────────────────────────────────────────────────
        game_name = parse_riot_id(riot_id)[0]

        embed = discord.Embed(
            title=f"⏱️ Distribución de duración de partidas — {riot_id}",
            description=(
                f"📊 **{stats['total_analyzed']}** partidas analizadas "
                f"(de {stats['total_fetched']} obtenidas"
                + (f", {stats['skipped_remakes']} remakes descartados" if stats["skipped_remakes"] else "")
                + f") | **{stats['win_rate']:.1f}%** WR general\n"
                f"🕒 Duración promedio: **{stats['avg_duration_min']:.1f} min**"
            ),
            color=0x00b4d8,
        )

        # One field per bucket
        lines = []
        for i, bucket in enumerate(buckets):
            if bucket["total"] == 0:
                continue
            emoji  = BUCKET_EMOJIS[i]
            bar    = _bar(bucket["pct"])
            wins   = bucket["wins"]
            losses = bucket["losses"]
            total  = bucket["total"]
            pct    = bucket["pct"]

            win_bar_len  = round(wins  / total * 8)
            loss_bar_len = round(losses / total * 8)
            wl_bar = "🟩" * win_bar_len + "🟥" * loss_bar_len

            lines.append(
                f"{emoji} **{bucket['label']}** — `{bar}` **{pct:.1f}%** ({total} partidas)\n"
                f"   {wl_bar}  ✅ {wins}V / ❌ {losses}D  "
                f"({bucket['win_pct']:.0f}% WR en este tramo)"
            )

        embed.add_field(
            name="📈 Distribución por duración:",
            value="\n".join(lines) if lines else "Sin datos",
            inline=False,
        )

        # Cumulative summary row
        n = stats["total_analyzed"]
        cum_lines = []
        running = 0
        for i, bucket in enumerate(buckets[:-1]):   # skip last (>30) – 100% by definition
            running += bucket["total"]
            cum_pct  = running / n * 100
            cum_wins = sum(b["wins"] for b in buckets[:i+1])
            cum_wr   = cum_wins / running * 100 if running else 0
            cum_lines.append(
                f"Antes de **{bucket['max']} min**: `{cum_pct:.1f}%` de partidas "
                f"({running}/{n}) — {cum_wr:.0f}% WR"
            )

        embed.add_field(
            name="📉 Acumulados:",
            value="\n".join(cum_lines) if cum_lines else "Sin datos",
            inline=False,
        )

        # Summoner profile icon
        if summoner_profile:
            icon_url = get_summoner_icon_url(summoner_profile["profileIconId"])
            embed.set_author(
                name=f"Nivel {summoner_profile['summonerLevel']}",
                icon_url=icon_url,
            )

        embed.set_footer(
            text="CapitanCoditos • Remakes (<5 min) excluidos del análisis"
        )

        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await handle_command_error(interaction, e)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_duracionpartidas(tree: app_commands.CommandTree):
    @app_commands.describe(
        riot_id="Tu Riot ID completo (ej: Roga#LAN)",
        partidas="Número de partidas a analizar",
        region="Región del servidor (default: LAN)",
    )
    @app_commands.choices(partidas=PARTIDAS_CHOICES, region=REGION_CHOICES)
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(
        name="duracionpartidas",
        description="Muestra qué % de tus partidas terminan antes del minuto 15, 20, 25 y 30 ⏱️",
    )
    async def command(
        interaction: discord.Interaction,
        riot_id: str,
        partidas: int = 50,
        region: str = "LAN",
    ):
        await duracion_partidas(interaction, riot_id, partidas, region)
