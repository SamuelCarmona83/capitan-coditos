import discord
from discord import app_commands
from riot.api import get_player_matchup_data, REGION_MAP
from utils.helpers import parse_riot_id, get_champion_icon_url, get_summoner_icon_url, handle_command_error
from utils.autocomplete import riot_id_autocomplete
from ai.openai_service import generar_analisis_matchups
from database import save_summoner

# Build region choices from the API region map
REGION_CHOICES = [
    app_commands.Choice(name=region, value=region)
    for region in REGION_MAP.keys()
]


async def matchups(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(riot_id)

        # Send progress message (keep reference to edit it later)
        # Estimate: ~1.3 sec per match = 130 sec for 100 matches = ~2 minutes
        estimated_time = int((partidas * 1.3) / 60)
        progress_msg = await interaction.followup.send(
            f"🔍 Analizando matchups de **{riot_id}** ({region}) en las últimas **{partidas}** partidas ranked...\n"
            f"⏳ Tiempo estimado: **~{estimated_time} minutos**. Esto descarga y analiza cada partida individualmente.",
            wait=True
        )

        # Progress callback: edit the same message instead of sending new ones
        async def progress_callback(current, total):
            try:
                pct = int((current / total) * 100)
                bar = '█' * (pct // 10) + '░' * (10 - pct // 10)
                await progress_msg.edit(
                    content=(
                        f"🔍 Analizando matchups de **{riot_id}** ({region})...\n"
                        f"📊 Progreso: **{current}/{total}** partidas [{bar}] {pct}%"
                    )
                )
            except Exception:
                pass

        # Fetch and analyze matchup data
        matchup_data, general_stats, summoner_profile = await get_player_matchup_data(
            riot_id, count=partidas, progress_callback=progress_callback, region=region
        )

        if not matchup_data:
            await interaction.followup.send("❌ No se encontraron matchups en partidas ranked en Grieta del Invocador.")
            return

        # Filter matchups with minimum 2 games and sort by worst win rate
        significant_matchups = {k: v for k, v in matchup_data.items() if v["games"] >= 2}

        if not significant_matchups:
            # Fall back to all matchups if none have 2+ games
            significant_matchups = matchup_data
            min_games_label = "1 partida"
        else:
            min_games_label = "2+ partidas"

        # Sort: worst win rate first, then by most games (for tie-breaking)
        worst_matchups = sorted(
            significant_matchups.items(),
            key=lambda x: (x[1]["wins"] / x[1]["games"], -x[1]["games"])
        )[:10]

        # Generate AI analysis
        game_name = parse_riot_id(riot_id)[0]
        ai_analysis = await generar_analisis_matchups(game_name, worst_matchups, general_stats)

        # Build matchup text for embed
        matchup_lines = []
        for i, (champ, data) in enumerate(worst_matchups[:10], 1):
            wr = (data["wins"] / data["games"]) * 100
            avg_kda = (data["kills"] + data["assists"]) / max(1, data["deaths"])
            # Top 2 picks used against this champion
            top_picks = ", ".join([
                c for c, _ in sorted(
                    data["player_champions"].items(),
                    key=lambda x: x[1]["games"], reverse=True
                )[:2]
            ])

            if wr == 0:
                emoji = "💀"
            elif wr < 35:
                emoji = "🔴"
            elif wr < 50:
                emoji = "🟠"
            else:
                emoji = "🟡"

            matchup_lines.append(
                f"{emoji} **vs {champ}** — `{data['wins']}W/{data['losses']}L` "
                f"({wr:.0f}%) | KDA: `{avg_kda:.1f}` | Con: {top_picks}"
            )

        matchup_text = "\n".join(matchup_lines)

        # Create embed
        embed = discord.Embed(
            title=f"� Matchups a Trabajar de {riot_id}",
            description=(
                f"📊 **{general_stats['total_analyzed']}** partidas ranked analizadas "
                f"(de {general_stats['total_fetched']} obtenidas) | "
                f"**{general_stats['win_rate']:.1f}%** WR general"
            ),
            color=0xff4444
        )

        # Matchups field (truncate if needed)
        if len(matchup_text) > 1020:
            matchup_text = matchup_text[:1017] + "..."
        embed.add_field(
            name=f"🎯 Matchups más difíciles ({min_games_label}):",
            value=matchup_text if matchup_text else "No hay suficientes datos",
            inline=False
        )

        # AI Analysis field
        if len(ai_analysis) > 1020:
            ai_analysis = ai_analysis[:1017] + "..."
        embed.add_field(
            name="🤖 Análisis de matchups:",
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

        # Nemesis: champions that kill the player the most
        killers = general_stats.get("killers", {})
        if killers:
            # Filter enemies faced at least 2 times, sort by avg kills per game
            nemesis_list = [
                (champ, data) for champ, data in killers.items()
                if data["games_against"] >= 2
            ]
            nemesis_list.sort(
                key=lambda x: x[1]["enemy_kills_total"] / x[1]["games_against"],
                reverse=True
            )
            top_nemesis = nemesis_list[:5]
            if top_nemesis:
                nemesis_lines = []
                for i, (champ, data) in enumerate(top_nemesis, 1):
                    avg_kills = data["enemy_kills_total"] / data["games_against"]
                    avg_deaths = data["player_deaths_in_games"] / data["games_against"]
                    medal = ["👑", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
                    
                    # Build match links for verification (LeagueOfGraphs format)
                    match_links = []
                    for match_id in data.get("match_ids", [])[:3]:  # Show max 3 games
                        # Extract platform and numeric ID from match_id (e.g., "LA1_1234567890")
                        parts = match_id.split("_")
                        if len(parts) == 2:
                            platform = parts[0].lower()  # e.g., "la1" -> "la1"
                            numeric_id = parts[1]
                            # Convert platform to region name for URL using shared REGION_MAP
                            region_code = REGION_MAP.get(platform, platform)
                            match_links.append(f"[G{len(match_links)+1}](https://www.leagueofgraphs.com/match/{region_code}/{numeric_id})")
                    
                    links_text = " | ".join(match_links) if match_links else ""
                    nemesis_lines.append(
                        f"{medal} **{champ}** — `{avg_kills:.1f}` kills/game promedio "
                        f"({data['games_against']} partidas) | Tus muertes: `{avg_deaths:.1f}`/game"
                        + (f"\n      Ver: {links_text}" if links_text else "")
                    )
                nemesis_text = "\n".join(nemesis_lines)
                if len(nemesis_text) > 1020:
                    nemesis_text = nemesis_text[:1017] + "..."
                embed.add_field(
                    name="🔪 Némesis (campeones que más te matan):",
                    value=nemesis_text,
                    inline=False
                )

        # Set the worst matchup champion as thumbnail
        if worst_matchups:
            worst_champ = worst_matchups[0][0]
            embed.set_thumbnail(url=get_champion_icon_url(worst_champ))

        # Summoner profile icon
        if summoner_profile:
            profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
            embed.set_author(
                name=f"Nivel {summoner_profile['summonerLevel']}",
                icon_url=profile_icon_url
            )

        embed.set_footer(
            text="CapitanCoditos, Tu afk favorito. • Solo partidas Ranked en Grieta del Invocador"
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await handle_command_error(interaction, e)


def register_matchups(tree):
    @app_commands.describe(
        riot_id="Tu Riot ID completo (ej: Roga#LAN)",
        partidas="Número de partidas ranked a analizar",
        region="Región del servidor (default: LAN)"
    )
    @app_commands.choices(
        partidas=[
            app_commands.Choice(name="25 partidas (rápido)", value=25),
            app_commands.Choice(name="50 partidas (recomendado)", value=50),
            app_commands.Choice(name="100 partidas (profundo)", value=100),
        ],
        region=REGION_CHOICES
    )
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(
        name="matchups",
        description="Analiza tus matchups más difíciles en ranked para identificar áreas de mejora 📈"
    )
    async def command(interaction: discord.Interaction, riot_id: str, partidas: int = 50, region: str = "LAN"):
        await matchups(interaction, riot_id, partidas, region)
