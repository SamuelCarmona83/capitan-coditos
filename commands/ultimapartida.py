import discord
from discord import app_commands
from riot.api import get_player_match_data
from utils.helpers import parse_riot_id, format_kda, get_match_result_info, create_stats_dict, handle_command_error, get_champion_icon_url
from ai.openai_service import generar_mensaje_openai

async def ultimapartida(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        participant, match_data, game_duration = await get_player_match_data(riot_id)
        game_name = parse_riot_id(riot_id)[0]
        
        champ = participant["championName"]
        kda = format_kda(participant)
        resultado, _ = get_match_result_info(participant)

        # TODO: handle game mode
        game_mode = match_data["info"]["gameMode"] or "Desconocido"
        
        stats = create_stats_dict(participant, game_duration)
        mensaje_openai = await generar_mensaje_openai(game_name, stats, participant, game_mode)
        
        # Create champion icon URL (Data Dragon API)
        champion_icon_url = get_champion_icon_url(champ)

        # Create Discord embed with champion icon
        embed = discord.Embed(
            title=f"Última partida de {riot_id}",
            description=f"🎯 KDA: {kda} | 🕹️ {resultado} | 🕒 {game_duration} minutos",
            color=0x00ff00 if resultado == "Victoria" else 0xff0000
        )
        
        # Custom mapping for game mode names
        custom_game_modes = {
            "CLASSIC": "Grieta del Invocador",
            "ARAM": "ARAM",
            "URF": "Ultra Rapid Fire",
            "CHERRY": "Arena de Noxus"
        }
        game_mode_name = custom_game_modes.get(game_mode, game_mode)
        
        embed.add_field(
            name=f"Campeón: {champ}",
            value=f"Modo de juego: {game_mode_name}",
            inline=False
        )
        
        embed.add_field(
            name="Análisis de la partida:",
            value=mensaje_openai,
            inline=False
        )
        
        embed.set_thumbnail(url=champion_icon_url)
        embed.set_footer(text="CapitanCoditos,Tu afk favorito.")

        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_ultimapartida(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
    @tree.command(name="ultimapartida", description="Consulta tu última partida de LoL usando Riot ID (Roga#LAN)")
    async def command(interaction: discord.Interaction, riot_id: str):
        await ultimapartida(interaction, riot_id)
