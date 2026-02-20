import os
from openai import AsyncOpenAI

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generar_mensaje_openai(nombre, stats, participant=None, game_mode="Desconocido"):
    """Generate sarcastic LoL coach message using OpenAI."""
    
    # Extract role-specific farming information
    role = stats.get('teamPosition', 'UNKNOWN')
    primary_farm = stats.get('primary_farm', 0)
    #primary_farm_type = stats.get('primary_farm_type', 'farm')
    secondary_farm = stats.get('secondary_farm', 0)
    #secondary_farm_type = stats.get('secondary_farm_type', 'farm secundario')
    role_expectations = stats.get('role_expectations', {})
    
    # Create role-specific farming analysis
    farm_analysis = ""
    if role == 'JUNGLE':
        farm_analysis = f"Monstruos de jungla: `{primary_farm}` | Súbditos robados: `{secondary_farm}`"
    elif role == 'UTILITY':  # Support
        farm_analysis = f"CS: `{primary_farm}` (correcto para support) | Monstruos: `{secondary_farm}`"
    else:  # Lanes (TOP, MID, BOT)
        farm_analysis = f"Súbditos: `{primary_farm}` | Monstruos de jungla: `{secondary_farm}`"

    if game_mode == "ARAM":
        vision_analysis = "En ARAM, el farmeo no es tan relevante, ni la visión, pero el daño a campeones es crucial."
    elif game_mode == "CLASSIC" or game_mode == "Grieta del invocador":
        vision_analysis = f"{stats.get('visionScore', 0)} (importante en modo CLASSIC)"
    else:
        vision_analysis = "En este modo de juego, la visión y el farmeo son menos relevantes."

    multikill_analysis = ""
    if participant.get('pentaKills', 'N/A'):
        multikill_analysis = f" | Pentakills: `{participant.get('pentaKills', 0)}` (¡Bien hecho!)"

    prompt = f"""
    Actúa como un entrenador de League of Legends brutalmente honesto y sarcástico.
    Genera un mensaje corto (máximo 2 oraciones) y directo usando el formato de texto de Discord:
    - Usa **negrita** para énfasis
    - Usa *cursiva* para términos de juego
    - Usa __subrayado__ para nombres
    - Usa ~~tachado~~ para errores o fallos
    - Usa `código` para números o estadísticas

    Estadísticas del jugador:
    Invocador: __**{nombre}**__
    Rol: `{role}`
    KDA: `{stats['kills']}/{stats['deaths']}/{stats['assists']}` (KDA: `{stats.get('kda', 'N/A'):.1f}`)
    Daño: `{stats['totalDamageDealtToChampions']:,}`
    Tiempo: `{stats['gameDuration']} min`
    Modo de juego: `{game_mode}`
    
    Análisis de farmeo {role}:
    {farm_analysis}
    {role_expectations.get(role, 'No hay expectativas específicas para este rol')}
    Nota: el farmeo es importante, pero solo en modo CLASSIC o Grieta del invocador.

    IMPORTANTE - Considera el rol del jugador si es modo de juego CLASSIC o Grieta del invocador:
    - Si es JUNGLE: Enfócate en los monstruos de jungla y daño a campeones, no en súbditos de carril.
    - Si es UTILITY (Support): No critiques el bajo CS, es normal para supports pero deberían influir más puntaje de visión.
    - Si es TOP/MID/BOTTOM: Enfócate en el farmeo de súbditos de carril y daño a campeones.

    Ten en cuenta estos otros detalles del jugador:
    - Campeón: `{participant.get('championName', 'N/A')}` (si está disponible)
    - Visión: `{vision_analysis}` 
    - Oro: `{stats.get('goldEarned', 'N/A')}` si es bajo dile "pelabolas", lo normal es más de 10k.
    - Nivel: `{stats.get('champLevel', 'N/A')}` si es bajo dile, menor que 14, "Traiganle una falda a la niña"
    - {multikill_analysis}

    Escribe un mensaje breve (máximo 2 oraciones ni mas ni menos), mencionando específicamente sus estadísticas. tambien le pudes decir casual.
    Haz comentarios pasivo agresivos como "Tienes una increible habilidad casi pareces Plata II" o "Eres un genio del LoL, deberías estar en Challenger"
    Si el jugador tuvo un buen desempeño, evalúa objetivamente su actuación y el campeón/rol jugado.
    Si el jugador tuvo un mal desempeño, utiliza un tono sarcástico y directo, como "Con ese KDA, deberías estar jugando en la liga de los bots" o "Tienes una increíble habilidad, casi pareces Plata II".
    Si puedes utiliza manera de hablar latinoamerica, coloquialismos que oscilen entre los diferentes paises de la region ( recuerda máximo 2 oraciones).
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Eres un jugador de LoL con humor ácido, opiniones fuertes y objetividad si el desempeño fue decente."
            },
            {
                "role": "user",
                "content": prompt + "\n\nSi el jugador realizó una buena actuación, evalúa objetivamente su desempeño. Y el campeon/rol jugado."
            }
        ],
        #temperature=0.8
    )

    return response.choices[0].message.content.strip()

async def generar_analisis_matchups(nombre, worst_matchups, general_stats):
    """Generate AI analysis of a player's worst matchups and weaknesses."""
    
    # Build matchup details string
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
    
    roles_text = ", ".join([f"{role}: {count}" for role, count in general_stats['roles_played'].items()])
    
    # Build nemesis info if available
    nemesis_text = ""
    killers = general_stats.get("killers", {})
    if killers:
        sorted_killers = sorted(
            [(champ, d) for champ, d in killers.items() if d["games_against"] >= 2],
            key=lambda x: x[1]["enemy_kills_total"] / x[1]["games_against"],
            reverse=True
        )[:5]
        if sorted_killers:
            nemesis_text = "\n    **Némesis (campeones que más lo matan):**\n"
            for champ, d in sorted_killers:
                avg_kills = d["enemy_kills_total"] / d["games_against"]
                avg_deaths = d["player_deaths_in_games"] / d["games_against"]
                nemesis_text += f"    - {champ}: promedio {avg_kills:.1f} kills por partida en {d['games_against']} juegos (jugador muere {avg_deaths:.1f} veces promedio)\n"
    
    prompt = f"""
    Actúa como un analista/coach de League of Legends brutalmente honesto y sarcástico.
    Analiza los peores matchups de un jugador y da consejos concretos para mejorar.

    **Jugador:** {nombre}
    **Estadísticas generales:** {general_stats['total_analyzed']} partidas ranked analizadas, {general_stats['win_rate']:.1f}% WR general
    **Roles jugados:** {roles_text}

    **Peores matchups (ordenados por winrate, mínimo 2 partidas):**
    {matchup_details}
    {nemesis_text}
    Genera un análisis de máximo 4-5 oraciones en español con estas reglas:
    1. Identifica el PATRÓN: ¿hay un tipo de campeón que le cuesta (asesinos, tanques, poke, bruisers)?
    2. Menciona sus picks más problemáticos contra esos campeones específicos
    3. Da UN consejo práctico y directo (banear algo, cambiar de pick, mejorar spacing, etc.)
    4. Si hay un matchup con 0% WR en varias partidas, hazle bullying especial
    5. Si hay datos de némesis, menciona al campeón que más lo asesina y búrlate de eso

    Usa formato Discord: **negrita**, *cursiva*, `código` para stats, __subrayado__ para énfasis.
    Usa coloquialismos latinoamericanos para hacerlo divertido y directo.
    Sé brutalmente honesto - si tiene un 0% WR contra algo, díselo sin filtro.
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Eres un analista de LoL con humor ácido que identifica debilidades de jugadores y da consejos prácticos. Hablas como latino."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return response.choices[0].message.content.strip()

async def generar_analisis_worst_games(nombre, worst_games, general_stats):
    """Generate AI analysis of a player's worst performances and patterns."""
    
    # Build worst games details
    games_details = ""
    for i, game in enumerate(worst_games[:10], 1):
        result = "Victoria" if game["won"] else "Derrota"
        games_details += (
            f"{i}. {game['champion']} ({game['position']}) - {result}: "
            f"{game['kills']}/{game['deaths']}/{game['assists']} (KDA {game['kda']:.2f}), "
            f"KP: {game['kill_participation']:.0f}%, Score: {game['score']:.1f}/100\n"
        )
    
    roles_text = ", ".join([f"{role}: {count}" for role, count in general_stats['roles_played'].items()])
    
    # Identify patterns
    worst_champions = {}
    worst_roles = {}
    total_deaths_in_worst = 0
    losses_in_worst = 0
    
    for game in worst_games:
        champ = game["champion"]
        role = game["position"]
        worst_champions[champ] = worst_champions.get(champ, 0) + 1
        worst_roles[role] = worst_roles.get(role, 0) + 1
        total_deaths_in_worst += game["deaths"]
        if not game["won"]:
            losses_in_worst += 1
    
    most_common_champ = max(worst_champions.items(), key=lambda x: x[1])[0] if worst_champions else "N/A"
    most_common_role = max(worst_roles.items(), key=lambda x: x[1])[0] if worst_roles else "N/A"
    avg_deaths_worst = total_deaths_in_worst / len(worst_games)
    
    prompt = f"""
    Actúa como un analista/coach de League of Legends brutalmente honesto y sarcástico.
    Analiza las 10 PEORES performances de un jugador en sus últimas {general_stats['total_analyzed']} ranked.

    **Jugador:** {nombre}
    **Estadísticas generales:** {general_stats['total_analyzed']} partidas analizadas, {general_stats['win_rate']:.1f}% WR
    **Promedios:** KDA {general_stats['avg_kda']:.2f}, {general_stats['avg_deaths']:.1f} muertes/game
    **Roles jugados:** {roles_text}

    **Las 10 peores partidas (score más bajo = peor performance):**
    {games_details}

    **Patrones identificados:**
    - Campeón más presente en sus peores juegos: {most_common_champ}
    - Rol más problemático: {most_common_role}
    - Muertes promedio en peores juegos: {avg_deaths_worst:.1f} (vs {general_stats['avg_deaths']:.1f} general)
    - Derrotas en top 10 peor: {losses_in_worst}/10

    Genera un análisis CORTO de máximo 2-3 oraciones en español:
    1. Identifica el PATRÓN más obvio (campeón/rol problemático, muchas muertes)
    2. Da UN consejo específico y directo
    3. Sé BRUTAL y al grano

    Usa formato Discord: **negrita** para énfasis y `código` para stats.
    Usa humor ácido latino. Máximo 3 oraciones.
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Eres un analista de LoL sin filtro que identifica los errores más graves de un jugador. Hablas como latino con humor ácido."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return response.choices[0].message.content.strip()
