import os
from openai import AsyncOpenAI

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generar_mensaje_openai(nombre, stats):
    """Generate sarcastic LoL coach message using OpenAI."""
    prompt = f"""
    Actúa como un entrenador de League of Legends brutalmente honesto y sarcástico.
    Genera un mensaje corto y directo usando el formato de texto de Discord:
    - Usa **negrita** para énfasis
    - Usa *cursiva* para términos de juego
    - Usa __subrayado__ para nombres
    - Usa ~~tachado~~ para errores o fallos
    - Usa `código` para números o estadísticas
    
    Estadísticas del jugador:
    Invocador: __**{nombre}**__
    KDA: `{stats['kills']}/{stats['deaths']}/{stats['assists']}`
    Daño: `{stats['totalDamageDealtToChampions']:,}`
    Tiempo: `{stats['gameDuration']} min`

    Escribe un mensaje breve (máximo 2 oraciones) con humor negro gamer, mencionando específicamente sus estadísticas.
    Usa memes de gaming, referencias a otros juegos más fáciles (Candy Crush, Minecraft, etc), o tiempo en pantalla gris.
    """

    response = await openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "Eres un jugador de LoL con humor ácido, opiniones fuertes y objetividad si el desempeño fue bueno."
            },
            {
                "role": "user",
                "content": prompt + "\n\nSi el jugador realizó una buena actuación, evalúa objetivamente su desempeño."
            }
        ],
        temperature=0.8
    )

    return response.choices[0].message.content.strip()
