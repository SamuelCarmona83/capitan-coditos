import discord
from discord import app_commands
from riot.api import get_player_match_data
from utils.helpers import parse_riot_id, format_kda, get_match_result_info, create_stats_dict, send_long_message, handle_command_error
from ai.openai_service import generar_mensaje_openai

async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        participant, _, game_duration = await get_player_match_data(riot_id)
        game_name = parse_riot_id(riot_id)[0]
        
        champ = participant["championName"]
        kda = format_kda(participant)
        resultado, _ = get_match_result_info(participant)
        
        stats = create_stats_dict(participant, game_duration)
        mensaje_openai = await generar_mensaje_openai(game_name, stats)

        full_message = (
            f"**{riot_id}** jugó como **{champ}**\n"
            f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {game_duration} minutos\n\n"
            f"{mensaje_openai}"
        )

        await send_long_message(interaction, full_message)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_ultimapartida(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str):
        await ultimapartida(interaction, riot_id)
