"""
OpenAI service. Migrated from app/ai/openai_service.py.
"""
import os

from openai import AsyncOpenAI

_client: AsyncOpenAI = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    return _client


async def generar_mensaje_openai(nombre: str, stats: dict, participant: dict, game_mode: str = "Desconocido") -> str:
    role = stats.get("teamPosition", "UNKNOWN")
    primary_farm = stats.get("primary_farm", 0)
    secondary_farm = stats.get("secondary_farm", 0)
    role_expectations = stats.get("role_expectations", {})

    if role == "JUNGLE":
        farm_analysis = f"Monstruos de jungla: `{primary_farm}` | Súbditos robados: `{secondary_farm}`"
    elif role == "UTILITY":
        farm_analysis = f"CS: `{primary_farm}` (correcto para support) | Monstruos: `{secondary_farm}`"
    else:
        farm_analysis = f"Súbditos: `{primary_farm}` | Monstruos de jungla: `{secondary_farm}`"

    if game_mode == "ARAM":
        vision_analysis = "En ARAM, el farmeo no es tan relevante, ni la visión, pero el daño a campeones es crucial."
    elif game_mode in ("CLASSIC", "Grieta del invocador"):
        vision_analysis = f"{stats.get('visionScore', 0)} (importante en modo CLASSIC)"
    else:
        vision_analysis = "En este modo de juego, la visión y el farmeo son menos relevantes."

    multikill = ""
    if participant.get("pentaKills"):
        multikill = f" | Pentakills: `{participant.get('pentaKills', 0)}`"

    prompt = f"""
    Actúa como un entrenador de League of Legends apasionado y motivador.
    Genera un mensaje corto (máximo 2 oraciones) y directo usando el formato de texto de Discord:
    - Usa **negrita** para énfasis, *cursiva* para términos de juego, `código` para números.

    Estadísticas del jugador:
    Invocador: __**{nombre}**__  Rol: `{role}`
    KDA: `{stats['kills']}/{stats['deaths']}/{stats['assists']}` (KDA: `{stats.get('kda', 0):.1f}`)
    Daño: `{stats['totalDamageDealtToChampions']:,}`  Tiempo: `{stats['gameDuration']} min`
    Modo: `{game_mode}`

    Análisis de farmeo {role}: {farm_analysis}
    {role_expectations}
    Visión: `{vision_analysis}` | Oro: `{stats.get('goldEarned', 'N/A')}` | Nivel: `{stats.get('champLevel', 'N/A')}`
    {multikill}

    Escribe máximo 2 oraciones, menciona estadísticas específicas.
    Si buen desempeño → celebra. Si margen mejora → consejo constructivo.
    Usa coloquialismos latinoamericanos.
    """

    response = await _get_client().chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Eres un coach de LoL con buen humor. Celebras logros y das consejos constructivos."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def generar_analisis_matchups(nombre: str, worst_matchups: list, general_stats: dict) -> str:
    matchup_details = ""
    for i, (champ, data) in enumerate(worst_matchups[:10], 1):
        wr = (data["wins"] / data["games"]) * 100
        avg_deaths = data["deaths"] / data["games"]
        avg_kda = (data["kills"] + data["assists"]) / max(1, data["deaths"])
        picks = ", ".join([
            f"{c} ({d['games']}j, {(d['wins']/d['games'])*100:.0f}%WR)"
            for c, d in sorted(data["player_champions"].items(), key=lambda x: x[1]["games"], reverse=True)[:3]
        ])
        matchup_details += (
            f"{i}. vs {champ}: {data['wins']}W/{data['losses']}L ({wr:.0f}% WR), "
            f"KDA prom: {avg_kda:.1f}, Muertes prom: {avg_deaths:.1f}, "
            f"Picks usados: {picks}\n"
        )

    roles_text = ", ".join([f"{r}: {c}" for r, c in general_stats["roles_played"].items()])

    nemesis_text = ""
    killers = general_stats.get("killers", {})
    if killers:
        sorted_killers = sorted(
            [(ch, d) for ch, d in killers.items() if d["games_against"] >= 2],
            key=lambda x: x[1]["enemy_kills_total"] / x[1]["games_against"],
            reverse=True,
        )[:5]
        if sorted_killers:
            nemesis_text = "\n    **Némesis:**\n"
            for ch, d in sorted_killers:
                avg_k = d["enemy_kills_total"] / d["games_against"]
                avg_d = d["player_deaths_in_games"] / d["games_against"]
                nemesis_text += f"    - {ch}: {avg_k:.1f} kills/game en {d['games_against']} juegos\n"

    prompt = f"""
    Analiza los matchups más difíciles de {nombre} ({general_stats['total_analyzed']} partidas, {general_stats['win_rate']:.1f}% WR).
    Roles: {roles_text}

    Matchups difíciles:
    {matchup_details}
    {nemesis_text}
    4-5 oraciones: identifica patrones, da UN consejo práctico. Usa formato Discord. Coloquialismos latinoamericanos.
    """

    response = await _get_client().chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Analista de LoL que identifica patrones y da consejos prácticos."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()


async def generar_analisis_worst_games(nombre: str, worst_games: list, general_stats: dict) -> str:
    games_details = ""
    for i, g in enumerate(worst_games[:10], 1):
        result = "Victoria" if g["won"] else "Derrota"
        games_details += (
            f"{i}. {g['champion']} ({g['position']}) - {result}: "
            f"{g['kills']}/{g['deaths']}/{g['assists']} (KDA {g['kda']:.2f}), "
            f"KP: {g['kill_participation']:.0f}%, Score: {g['score']:.1f}/100\n"
        )

    roles_text = ", ".join([f"{r}: {c}" for r, c in general_stats["roles_played"].items()])

    worst_champs = {}
    for g in worst_games:
        worst_champs[g["champion"]] = worst_champs.get(g["champion"], 0) + 1

    prompt = f"""
    Analiza las peores partidas de {nombre}.
    {general_stats['total_analyzed']} partidas analizadas, {general_stats['win_rate']:.1f}% WR,
    KDA prom: {general_stats['avg_kda']:.2f}, muertes prom: {general_stats['avg_deaths']:.1f}
    Roles: {roles_text}

    Top 10 peores partidas (score más bajo):
    {games_details}

    4-5 oraciones: identifica patrones de bajo rendimiento, da consejos concretos de mejora.
    Usa formato Discord. Coloquialismos latinoamericanos.
    """

    response = await _get_client().chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Analista de LoL que ayuda a mejorar identificando patrones negativos."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip()
