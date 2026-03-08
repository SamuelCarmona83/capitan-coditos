"""
Discord embed builders.
All functions receive plain Python dicts (from API response JSON)
and return discord.Embed (or View) objects.
No Riot API calls here.
"""
import discord


# ---------------------------------------------------------------------------
# URL helpers (duplicate from api/services/match_logic.py – kept local
# so the bot has no dependency on the api/ package)
# ---------------------------------------------------------------------------

_CHAMPION_SPECIAL_CASES = {
    "Wukong": "MonkeyKing",
    "Nunu & Willump": "Nunu",
    "Cho'Gath": "Chogath",
    "Kai'Sa": "Kaisa",
    "Kha'Zix": "Khazix",
    "Kog'Maw": "KogMaw",
    "LeBlanc": "Leblanc",
    "Vel'Koz": "Velkoz",
    "Rek'Sai": "RekSai",
    "Renata Glasc": "Renata",
    "Bel'Veth": "Belveth",
}
_GAME_MODE_LABELS = {
    "CLASSIC": "Grieta del Invocador",
    "ARAM": "ARAM",
    "ARAM_MAYHEM": "ARAM Caos",
    "ODIN": "ARAM",
    "URF": "Ultra Rapid Fire",
    "CHERRY": "Arena de Noxus",
    "ULTBOOK": "Libro de Hechizos",
}
_REGION_URL_MAP = {
    "la1": "lan", "la2": "las", "na1": "na", "br1": "br",
    "euw1": "euw", "eun1": "eune", "tr1": "tr", "ru": "ru",
    "kr": "kr", "jp1": "jp", "oc1": "oce",
    "ph2": "ph", "sg2": "sg", "th2": "th", "tw2": "tw", "vn2": "vn",
}


def _champ_url(name: str, version: str = "15.14.1") -> str:
    formatted = _CHAMPION_SPECIAL_CASES.get(name, name)
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{formatted}.png"


def _icon_url(icon_id: int, version: str = "15.14.1") -> str:
    return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{icon_id}.png"


def _game_mode_label(mode: str) -> str:
    return _GAME_MODE_LABELS.get(mode, mode)


def _match_url(match_id: str) -> str:
    """Build a LeagueOfGraphs link from a match ID like LA1_1234567890."""
    parts = match_id.split("_")
    if len(parts) == 2:
        platform = parts[0].lower()
        numeric = parts[1]
        region = _REGION_URL_MAP.get(platform, platform)
        return f"https://www.leagueofgraphs.com/match/{region}/{numeric}"
    return ""


def _truncate(s: str, limit: int = 1020) -> str:
    return s[:limit - 3] + "..." if len(s) > limit else s


def _set_author(embed: discord.Embed, summoner_profile: dict):
    if summoner_profile:
        embed.set_author(
            name=f"Nivel {summoner_profile.get('summonerLevel', '?')}",
            icon_url=_icon_url(summoner_profile.get("profileIconId", 0)),
        )


# ---------------------------------------------------------------------------
# Last-match embed
# ---------------------------------------------------------------------------

def build_last_match_embed(api_response: dict) -> discord.Embed:
    """Build embed from GET /summoner/<id>/last-match response."""
    participant = api_response["participant"]
    riot_id = api_response["riot_id"]
    game_duration = api_response["game_duration"]
    summoner_profile = api_response.get("summoner_profile")
    analysis = api_response.get("analysis")
    valid = api_response.get("valid_for_analysis", True)
    game_mode = api_response.get("game_mode", "Desconocido")
    game_mode_label = api_response.get("game_mode_label", _game_mode_label(game_mode))

    champ = participant["championName"]
    kda_str = f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"
    resultado = "Victoria" if participant["win"] else "Derrota"

    embed = discord.Embed(
        title=f"Última partida de {riot_id}",
        description=f"🎯 KDA: {kda_str} | 🕹️ {resultado} | 🕒 {game_duration} minutos",
        color=0x00FF00 if participant["win"] else 0xFF0000,
    )
    embed.add_field(name=f"Campeón: {champ}", value=f"Modo: {game_mode_label}", inline=False)

    if analysis:
        embed.add_field(name="Análisis:", value=_truncate(analysis), inline=False)
    elif not valid:
        embed.add_field(
            name="Estado:",
            value="⚠️ Partida muy corta o remake — sin análisis.",
            inline=False,
        )

    embed.set_thumbnail(url=_champ_url(champ))
    _set_author(embed, summoner_profile)
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    return embed


# ---------------------------------------------------------------------------
# Match history embed + view
# ---------------------------------------------------------------------------

def build_match_history_embed(api_response: dict) -> discord.Embed:
    """Build overview embed from GET /summoner/<id>/match-history response."""
    riot_id = api_response["riot_id"]
    matches = api_response["matches"]
    summoner_profile = api_response.get("summoner_profile")

    total_wins = sum(1 for m in matches if m["participant"]["win"])
    total_k = sum(m["participant"]["kills"] for m in matches)
    total_d = sum(m["participant"]["deaths"] for m in matches)
    total_a = sum(m["participant"]["assists"] for m in matches)
    wr = (total_wins / len(matches)) * 100 if matches else 0
    avg_kda = (total_k + total_a) / max(1, total_d)

    mode_map = {"CLASSIC": "Grieta", "ARAM": "ARAM", "ARAM_MAYHEM": "ARAM Caos", "ODIN": "ARAM", "URF": "URF", "CHERRY": "Arena", "ULTBOOK": "Libro de Hechizos"}
    summaries = []
    for i, m in enumerate(matches):
        p = m["participant"]
        emoji = "🏆" if p["win"] else "💔"
        mode = mode_map.get(m["game_mode"], m["game_mode"])
        kda_str = f"{p['kills']}/{p['deaths']}/{p['assists']}"
        summaries.append(
            f"`{i+1}.` {emoji} **{p['championName']}** — {kda_str} | {mode} ({m['game_duration']}min)"
        )

    embed = discord.Embed(
        title=f"Historial de {riot_id} (Últimas {len(matches)} partidas)",
        description=f"🏆 **{wr:.0f}% WR** | 📊 **{avg_kda:.1f} KDA promedio**",
        color=0x00FF00 if wr >= 50 else 0xFF9900 if wr >= 30 else 0xFF0000,
    )
    embed.add_field(name="📋 Partidas recientes:", value="\n".join(summaries), inline=False)
    _set_author(embed, summoner_profile)
    embed.set_footer(text="CapitanCoditos • Clic en una partida para ver el análisis detallado.")
    return embed


def build_match_detail_embed(
    riot_id: str, match: dict, match_number: int, analysis: str | None
) -> discord.Embed:
    """Build single-match detail embed (used for history button callbacks)."""
    p = match["participant"]
    champ = p["championName"]
    kda_str = f"{p['kills']}/{p['deaths']}/{p['assists']}"
    resultado = "Victoria" if p["win"] else "Derrota"
    mode_label = match.get("game_mode_label", _game_mode_label(match.get("game_mode", "")))
    damage = p.get("totalDamageDealtToChampions", 0)
    gold = p.get("goldEarned", 0)
    vision = p.get("visionScore", 0)
    cs = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)

    embed = discord.Embed(
        title=f"Partida #{match_number} — {riot_id}",
        description=f"🎯 **{kda_str}** | 🕹️ **{resultado}** | 🕒 **{match['game_duration']} min**",
        color=0x00FF00 if p["win"] else 0xFF0000,
    )
    embed.add_field(
        name=f"🏆 {champ} — {mode_label}",
        value=f"💰 **{gold:,}** oro | 👁️ **{vision}** visión | ⚔️ **{damage:,}** daño | 🗡️ **{cs}** CS",
        inline=False,
    )
    if analysis:
        embed.add_field(name="🤖 Análisis:", value=_truncate(analysis), inline=False)
    else:
        embed.add_field(name="Estado:", value="⚠️ Partida corta o remake — sin análisis.", inline=False)

    embed.set_thumbnail(url=_champ_url(champ))
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    return embed


# ---------------------------------------------------------------------------
# Team analysis embed + view
# ---------------------------------------------------------------------------

def build_team_analysis_embed(api_response: dict) -> discord.Embed:
    riot_id = api_response["riot_id"]
    participant = api_response["participant"]
    game_duration = api_response["game_duration"]
    summoner_profile = api_response.get("summoner_profile")
    worst_name = api_response.get("worst_player_name", "?")
    worst = api_response.get("worst_player", {})
    analysis = api_response.get("analysis")
    valid = api_response.get("valid_for_analysis", True)
    allies = api_response.get("allies", [])
    game_mode = api_response.get("game_mode", "Desconocido")
    game_mode_label = api_response.get("game_mode_label", _game_mode_label(game_mode))

    resultado = "Victoria" if participant["win"] else "Derrota"

    embed = discord.Embed(
        title=f"Análisis de partida de {riot_id}",
        description=f"🕒 {game_duration} min | 🕹️ {resultado} | {game_mode_label}",
        color=0x00FF00 if participant["win"] else 0xFF0000,
    )

    if not valid:
        embed.add_field(name="Estado:", value="⚠️ Partida corta/remake — sin análisis del equipo.", inline=False)
    else:
        if worst:
            kda = f"{worst['kills']}/{worst['deaths']}/{worst['assists']}"
            embed.add_field(
                name=f"⚠️ Jugador a mejorar: {worst_name}",
                value=f"{worst.get('championName', '?')} — KDA: {kda}",
                inline=False,
            )
        if analysis:
            embed.add_field(name="🤖 Análisis:", value=_truncate(analysis), inline=False)

        # Team roster
        roster = "\n".join(
            f"• **{p.get('riotIdGameName', p.get('summonerName', '?'))}** — "
            f"{p['championName']} (`{p['kills']}/{p['deaths']}/{p['assists']}`)"
            for p in allies
        )
        if roster:
            embed.add_field(name="👥 Equipo:", value=_truncate(roster), inline=False)

    embed.set_thumbnail(url=_champ_url(worst.get("championName", "Ahri")))
    _set_author(embed, summoner_profile)
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    return embed


# ---------------------------------------------------------------------------
# Matchups embed
# ---------------------------------------------------------------------------

def build_matchups_embed(result: dict) -> discord.Embed:
    """Build embed from Celery task result (run_matchups_task)."""
    if result.get("error"):
        return discord.Embed(
            title="❌ No se pudo completar el análisis",
            description=result["error"],
            color=0xFF4444,
        )

    riot_id = result["riot_id"]
    worst_matchups = result.get("worst_matchups", [])  # [[champ, data], ...]
    general_stats = result.get("general_stats", {})
    summoner_profile = result.get("summoner_profile")
    analysis = result.get("analysis", "")

    embed = discord.Embed(
        title=f"🎯 Matchups a Trabajar de {riot_id}",
        description=(
            f"📊 **{general_stats.get('total_analyzed', 0)}** partidas ranked analizadas "
            f"(de {general_stats.get('total_fetched', 0)}) | "
            f"**{general_stats.get('win_rate', 0):.1f}%** WR general"
        ),
        color=0xFF4444,
    )

    lines = []
    for champ, data in worst_matchups[:10]:
        wr = (data["wins"] / data["games"]) * 100
        avg_kda = (data["kills"] + data["assists"]) / max(1, data["deaths"])
        top_picks = ", ".join([
            c for c, _ in sorted(data["player_champions"].items(), key=lambda x: x[1]["games"], reverse=True)[:2]
        ])
        emoji = "💀" if wr == 0 else "🔴" if wr < 35 else "🟠" if wr < 50 else "🟡"
        lines.append(
            f"{emoji} **vs {champ}** — `{data['wins']}W/{data['losses']}L` "
            f"({wr:.0f}%) | KDA: `{avg_kda:.1f}` | Con: {top_picks}"
        )

    embed.add_field(name="🎯 Matchups más difíciles:", value=_truncate("\n".join(lines)) if lines else "—", inline=False)
    if analysis:
        embed.add_field(name="🤖 Análisis:", value=_truncate(analysis), inline=False)

    roles_map = {"TOP": "🗡️", "JUNGLE": "🌿", "MIDDLE": "🔮", "BOTTOM": "🏹", "UTILITY": "🛡️"}
    roles_text = " | ".join([
        f"{roles_map.get(r, '🎮')} **{r}**: {c}"
        for r, c in sorted(general_stats.get("roles_played", {}).items(), key=lambda x: x[1], reverse=True)
    ])
    if roles_text:
        embed.add_field(name="🎮 Roles:", value=roles_text, inline=False)

    top_champs = sorted(general_stats.get("champions_played", {}).items(), key=lambda x: x[1]["games"], reverse=True)[:5]
    if top_champs:
        embed.add_field(
            name="🏆 Campeones más jugados:",
            value=" | ".join(f"**{c}** ({d['games']}j, {(d['wins']/d['games'])*100:.0f}%)" for c, d in top_champs),
            inline=False,
        )

    # Nemesis
    killers = general_stats.get("killers", {})
    nemesis_list = [(ch, d) for ch, d in killers.items() if d["games_against"] >= 2]
    nemesis_list.sort(key=lambda x: x[1]["enemy_kills_total"] / x[1]["games_against"], reverse=True)
    if nemesis_list[:5]:
        medals = ["👑", "🥈", "🥉", "4️⃣", "5️⃣"]
        nemesis_lines = []
        for i, (ch, d) in enumerate(nemesis_list[:5]):
            avg_k = d["enemy_kills_total"] / d["games_against"]
            links = []
            for mid in d.get("match_ids", [])[:3]:
                url = _match_url(mid)
                if url:
                    links.append(f"[🔗]({url})")
            nemesis_lines.append(
                f"{medals[i]} **{ch}** — `{avg_k:.1f}` kills/game ({d['games_against']} partidas)"
                + (f" {' '.join(links)}" if links else "")
            )
        embed.add_field(name="🔪 Némesis:", value=_truncate("\n".join(nemesis_lines)), inline=False)

    _set_author(embed, summoner_profile)
    return embed


# ---------------------------------------------------------------------------
# Worst games embed
# ---------------------------------------------------------------------------

def build_worst_games_embed(result: dict) -> discord.Embed:
    """Build embed from Celery task result (run_worst_games_task)."""
    from datetime import datetime

    if result.get("error"):
        return discord.Embed(
            title="❌ No se pudo completar el análisis",
            description=result["error"],
            color=0xFF4444,
        )

    riot_id = result["riot_id"]
    worst_games = result.get("worst_games", [])
    general_stats = result.get("general_stats", {})
    summoner_profile = result.get("summoner_profile")
    analysis = result.get("analysis", "")
    role_filter = general_stats.get("filtered_role")
    role_title = f" ({role_filter})" if role_filter else ""

    embed = discord.Embed(
        title=f"📈 Análisis de Rendimiento de {riot_id}{role_title}",
        description=(
            f"📊 **{general_stats.get('total_analyzed', 0)}** partidas analizadas "
            f"(de {general_stats.get('total_fetched', 0)}) | "
            f"**{general_stats.get('win_rate', 0):.1f}%** WR\n"
            f"KDA prom: **{general_stats.get('avg_kda', 0):.2f}** | "
            f"Muertes prom: **{general_stats.get('avg_deaths', 0):.1f}**"
        ),
        color=0x8B0000,
    )

    lines = []
    for i, g in enumerate(worst_games, 1):
        emoji = "✅" if g["won"] else "❌"
        date_str = datetime.fromtimestamp(g["timestamp"] / 1000).strftime("%d/%m/%Y") if g.get("timestamp") else "?"
        url = _match_url(g["match_id"])
        link = f"[🔗 Ver]({url})" if url else ""
        lines.append(
            f"{i}. {emoji} **{g['champion']}** ({g['position']}) `{date_str}` — "
            f"`{g['kills']}/{g['deaths']}/{g['assists']}` KDA: `{g['kda']:.2f}` "
            f"Score: `{g['score']:.0f}/100` {link}"
        )

    embed.add_field(name="🎯 Top 10 Peores Partidas:", value=_truncate("\n".join(lines)) if lines else "—", inline=False)
    if analysis:
        embed.add_field(name="🤖 Análisis:", value=_truncate(analysis), inline=False)

    roles_map = {"TOP": "🗡️", "JUNGLE": "🌿", "MIDDLE": "🔮", "BOTTOM": "🏹", "UTILITY": "🛡️"}
    roles_text = " | ".join([
        f"{roles_map.get(r, '🎮')} **{r}**: {c}"
        for r, c in sorted(general_stats.get("roles_played", {}).items(), key=lambda x: x[1], reverse=True)
    ])
    if roles_text:
        embed.add_field(name="🎮 Roles:", value=roles_text, inline=False)

    top_champs = sorted(general_stats.get("champions_played", {}).items(), key=lambda x: x[1]["games"], reverse=True)[:5]
    if top_champs:
        embed.add_field(
            name="🏆 Campeones más jugados:",
            value=" | ".join(f"**{c}** ({d['games']}j, {(d['wins']/d['games'])*100:.0f}%)" for c, d in top_champs),
            inline=False,
        )

    _set_author(embed, summoner_profile)
    embed.set_footer(text="Score: KDA (35%) + KP (25%) + Daño (25%) + Visión (15%). Derrotas -20%.")
    return embed


# ---------------------------------------------------------------------------
# DB stats embed
# ---------------------------------------------------------------------------

def build_db_stats_embed(stats: dict) -> discord.Embed:
    embed = discord.Embed(title="📊 Estadísticas de la Base de Datos", color=0x0099FF)
    embed.add_field(name="👥 Invocadores Guardados", value=f"**{stats['total_summoners']}** únicos", inline=True)
    embed.add_field(name="🔍 Búsquedas Totales", value=f"**{stats['total_searches']}**", inline=True)
    if stats["total_summoners"] > 0:
        avg = stats["total_searches"] / stats["total_summoners"]
        embed.add_field(name="📈 Promedio", value=f"**{avg:.1f}** por invocador", inline=True)
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    return embed


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def handle_command_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, ValueError):
        await interaction.followup.send(f"⚠️ {error}")
    else:
        await interaction.followup.send(f"❌ Error: {error}")
