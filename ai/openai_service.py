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
    #role_expectations = stats.get('role_expectations', {})
    
    # Create role-specific farming analysis
    farm_analysis = ""
    if role == 'JUNGLE':
        farm_analysis = f"Monstruos de jungla: `{primary_farm}` | Súbditos robados: `{secondary_farm}`"
    elif role == 'UTILITY':  # Support
        farm_analysis = f"CS: `{primary_farm}` (correcto para support) | Monstruos: `{secondary_farm}`"
    else:  # Lanes (TOP, MID, BOT)
        farm_analysis = f"Súbditos: `{primary_farm}` | Monstruos de jungla: `{secondary_farm}`"
    
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
    {farm_analysis}
    nota: el farmeo es importante, pero solo en modo CLASSIC o Grieta del invocador.
    
    Modo de juego: `{game_mode}`

    IMPORTANTE - Considera el rol del jugador:
    - Si es JUNGLE: Enfócate en los monstruos de jungla, no en súbditos de carril
    - Si es UTILITY (Support): No critiques el bajo CS, es normal para supports
    - Si es TOP/MID/BOTTOM: Enfócate en el farmeo de súbditos de carril

    Ten en cuenta estos otros detalles del jugador:
    - Campeón: `{participant.get('championName', 'N/A')}` (si está disponible)
    - Visión: `{stats.get('visionScore', 'N/A')}` (para supports debería ser alto, solo importante en CLASSIC o grieta del invocador)
    - Oro: `{stats.get('goldEarned', 'N/A')}` si es bajo dile "pelabolas"
    - Nivel: `{stats.get('champLevel', 'N/A')}` si es bajo dile, menor que 14, "Traiganle una falda a la niña"
    - Pentakills: `{participant.get('pentaKills', 'N/A')}` (si está disponible)
    - Daño al equipo: `{participant.get('totalDamageDealtToChampions', 0)}` (si es bajo y jugó soporte no lo molestes, 
    sino dile Vegano o pacifista o que odias la carne de vacuno)

    Escribe un mensaje breve (máximo 2 oraciones ni mas ni menos) con humor negro gamer, mencionando específicamente sus estadísticas.
    Usa memes de gaming, referencias a otros juegos más fáciles o juegos para nenes pero de manera ocasional. tambien le pudes decir casual.
    (Candy Crush, Minecraft, etc), o tiempo en pantalla gris, mandalos a ver pocoyo. Haz comentarios pasivo agresivos como "Tienes una increible habilidad casi pareces Plata II"
    Si puedes utiliza manera de hablar latinoamerica, coloquialismos que oscilen entre los diferentes paises de la region (máximo 2 oraciones).
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
        temperature=0.8
    )

    return response.choices[0].message.content.strip()
