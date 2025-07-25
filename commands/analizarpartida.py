import discord
from discord import app_commands
from riot.api import get_player_match_data
from utils.helpers import encontrar_peor_jugador, create_stats_dict, get_player_name, format_kda, get_match_result_info, handle_command_error, get_champion_icon_url
from ai.openai_service import generar_mensaje_openai

async def analizar_partida(interaction: discord.Interaction, invocador: str):
    await interaction.response.defer()

    try:
        participant, match_data, game_duration = await get_player_match_data(invocador)
        participants = match_data['info']['participants']
        
        # Get allies (same team as the player)
        player_team = participant['teamId']
        aliados = [p for p in participants if p['teamId'] == player_team]
          # Analyze the worst player from the ally team
        peor_nombre, peor_stats, _ = encontrar_peor_jugador(aliados)
        game_mode = match_data["info"].get("gameMode", "Desconocido")
        stats = create_stats_dict(peor_stats, game_duration)
        mensaje = await generar_mensaje_openai(peor_nombre, stats, peor_stats, game_mode)
        
        # Format team stats
        resumen_equipo = "\n".join([
            f"• **{get_player_name(p)}** - {p['championName']} (`{format_kda(p)}`)"
            for p in aliados
        ])

        resultado, emoji_resultado = get_match_result_info(participant)

        # Create formatted message
        mensaje_formateado = (
            f"{emoji_resultado} **{resultado}** - ⏱️ {game_duration} min\n"
            f"**Equipo de {invocador}:**\n"
            f"{resumen_equipo}\n"
            f"\n{mensaje}"
        )

        await interaction.followup.send(mensaje_formateado)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_analizarpartida(tree):
    @app_commands.describe(invocador="Tu nombre de invocador (ej: Roga#LAN)")
    @tree.command(name="analizarpartida", description="Analiza tu última partida y encuentra al peor jugador con un resumen divertido.")
    async def command(interaction: discord.Interaction, invocador: str):
        await analizar_partida(interaction, invocador)
