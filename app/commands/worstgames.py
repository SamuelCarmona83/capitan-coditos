import discord
from discord import app_commands
from riot.api import get_worst_performances, REGION_MAP
from utils.helpers import parse_riot_id, handle_command_error
from utils.autocomplete import riot_id_autocomplete
from ai.openai_service import generar_analisis_worst_games
from database import save_summoner
from datetime import datetime

# Build region choices from the API region map
REGION_CHOICES = [
    app_commands.Choice(name=region, value=region)
    for region in REGION_MAP.keys()
]

# Partidas choices
PARTIDAS_CHOICES = [
    app_commands.Choice(name="100 partidas", value=100),
    app_commands.Choice(name="200 partidas", value=200),
    app_commands.Choice(name="250 partidas", value=250),
]

# Role choices
ROLE_CHOICES = [
    app_commands.Choice(name="Todos los roles", value="ALL"),
    app_commands.Choice(name="🗡️ TOP", value="TOP"),
    app_commands.Choice(name="🌿 JUNGLE", value="JUNGLE"),
    app_commands.Choice(name="🔮 MIDDLE", value="MIDDLE"),
    app_commands.Choice(name="🏹 BOTTOM (ADC)", value="BOTTOM"),
    app_commands.Choice(name="🛡️ UTILITY (Support)", value="UTILITY"),
]


async def worstgames(interaction: discord.Interaction, riot_id: str, partidas: int = 250, region: str = "LAN", rol: str = "ALL"):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(riot_id)

        # Send progress message
        estimated_time = int((partidas * 1.3) / 60)
        role_filter = None if rol == "ALL" else rol
        role_text = f" (solo {rol})" if role_filter else ""
        progress_msg = await interaction.followup.send(
            f"🔍 Analizando el **rendimiento** de **{riot_id}** ({region}){role_text} "
            f"en las últimas **{partidas}** partidas ranked...\n"
            f"⏳ Tiempo estimado: **~{estimated_time} minutos**. Calculando scores de rendimiento...",
            wait=True
        )

        # Progress callback: edit the same message
        async def progress_callback(current, total):
            try:
                pct = int((current / total) * 100)
                bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
                await progress_msg.edit(
                    content=(
                        f"🔍 Analizando **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** partidas [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        # Fetch and analyze worst performances
        worst_games, general_stats, summoner_profile = await get_worst_performances(
            riot_id, count=partidas, progress_callback=progress_callback, region=region, role=role_filter
        )

        if not worst_games:
            await interaction.followup.send("❌ No se encontraron suficientes partidas ranked para analizar.")
            return

        # Generate AI analysis
        game_name = parse_riot_id(riot_id)[0]
        ai_analysis = await generar_analisis_worst_games(game_name, worst_games, general_stats)

        # Build embed
        role_title = f" ({role_filter})" if role_filter else ""
        embed = discord.Embed(
            title=f"� Análisis de Rendimiento de {riot_id}{role_title}",
            description=(
                f"📊 **{general_stats['total_analyzed']}** partidas analizadas{role_text} "
                f"(de {general_stats['total_fetched']} obtenidas) | "
                f"**{general_stats['win_rate']:.1f}%** WR\n"
                f"📈 Promedios: KDA **{general_stats['avg_kda']:.2f}** | "
                f"**{general_stats['avg_deaths']:.1f}** muertes/game"
            ),
            color=0x8B0000  # Dark red
        )

        # Worst games list with links
        games_lines = []
        for i, game in enumerate(worst_games, 1):
            result_emoji = "✅" if game["won"] else "❌"
            
            # Format date from timestamp (milliseconds to datetime)
            if game.get("timestamp", 0) > 0:
                game_date = datetime.fromtimestamp(game["timestamp"] / 1000)
                date_str = game_date.strftime("%d/%m/%Y")
            else:
                date_str = "Fecha desconocida"
            
            # Build LeagueOfGraphs link
            parts = game["match_id"].split("_")
            game_link = ""
            if len(parts) == 2:
                platform = parts[0].lower()
                numeric_id = parts[1]
                region_map_url = {
                    "la1": "lan", "la2": "las", "na1": "na", "br1": "br",
                    "euw1": "euw", "eun1": "eune", "tr1": "tr", "ru": "ru",
                    "kr": "kr", "jp1": "jp", "oc1": "oce",
                    "ph2": "ph", "sg2": "sg", "th2": "th", "tw2": "tw", "vn2": "vn"
                }
                region_code = region_map_url.get(platform, platform)
                game_link = f"https://www.leagueofgraphs.com/match/{region_code}/{numeric_id}"
            
            # Format line
            link_text = f"[🔗 Ver]({game_link})" if game_link else ""
            games_lines.append(
                f"{i}. {result_emoji} **{game['champion']}** ({game['position']}) `{date_str}` — "
                f"`{game['kills']}/{game['deaths']}/{game['assists']}` "
                f"KDA: `{game['kda']:.2f}` | Score: `{game['score']:.0f}/100` {link_text}"
            )

        games_text = "\n".join(games_lines)
        if len(games_text) > 1020:
            games_text = games_text[:1017] + "..."
        
        embed.add_field(
            name="🎯 Top 10 Partidas con Menor Rendimiento (score más bajo = más margen de mejora):",
            value=games_text if games_text else "No hay datos",
            inline=False
        )

        # AI Analysis
        if len(ai_analysis) > 1020:
            ai_analysis = ai_analysis[:1017] + "..."
        embed.add_field(
            name="🤖 Análisis de patrones y áreas a mejorar:",
            value=ai_analysis,
            inline=False
        )

        # Roles played
        roles_map = {"TOP": "🗡️", "JUNGLE": "🌿", "MIDDLE": "🔮", "BOTTOM": "🏹", "UTILITY": "🛡️"}
        roles_text = " | ".join([
            f"{roles_map.get(role, '🎮')} **{role}**: {count}"
            for role, count in sorted(
                general_stats['roles_played'].items(),
                key=lambda x: x[1], reverse=True
            )
        ])
        embed.add_field(name="🎮 Roles jugados:", value=roles_text, inline=False)

        # Top champions played
        top_champs = sorted(
            general_stats['champions_played'].items(),
            key=lambda x: x[1]["games"], reverse=True
        )[:5]
        if top_champs:
            champs_text = " | ".join([
                f"**{c}** ({d['games']}j, {(d['wins']/d['games'])*100:.0f}%)"
                for c, d in top_champs
            ])
            embed.add_field(name="🏆 Campeones más jugados:", value=champs_text, inline=False)

        # Footer with methodology
        embed.set_footer(
            text="Score calculado: KDA (35%) + Kill Participation (25%) + Damage Share (25%) + Vision (15%). Derrotas tienen -20% penalty."
        )

        # Send embed
        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await handle_command_error(interaction, e)
    except Exception as e:
        await handle_command_error(interaction, e)


def register_worstgames(tree: app_commands.CommandTree):
    """Register the worstgames command to the tree"""
    
    @app_commands.choices(
        partidas=PARTIDAS_CHOICES,
        region=REGION_CHOICES,
        rol=ROLE_CHOICES
    )
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(
        name="worstgames",
        description="Analiza las partidas con menor rendimiento de un jugador en ranked 📈"
    )
    async def command(interaction: discord.Interaction, riot_id: str, partidas: int = 250, region: str = "LAN", rol: str = "ALL"):
        await worstgames(interaction, riot_id, partidas, region, rol)

