import discord
from discord import app_commands
from utils.helpers import encontrar_peor_jugador, create_stats_dict, get_player_name, format_kda, get_match_result_info, handle_command_error, get_champion_icon_url, get_match_analysis_data, create_ultima_partida_embed
from utils.autocomplete import riot_id_autocomplete
from ai.openai_service import generar_mensaje_openai
from database import save_summoner

def get_player_riot_id(participant):
    """Extract full Riot ID from participant data (Name#Tag format)"""
    game_name = participant.get('riotIdGameName')
    tag_line = participant.get('riotIdTagline')  # Fixed: was 'riotIdTagLine'
    
    # Debug logging
    #print(f"Debug: game_name='{game_name}', tag_line='{tag_line}'")
    
    if game_name and tag_line:
        riot_id = f"{game_name}#{tag_line}"
        #print(f"Debug: Created Riot ID: {riot_id}")
        return riot_id
    
    # If we don't have both parts, we can't create a valid Riot ID
    # Return None so the button gets disabled
    #print(f"Debug: Cannot create Riot ID, missing data")
    return None

async def show_player_ultima_partida(interaction: discord.Interaction, riot_id: str):
    """Helper function to show a player's last match - simplified using shared functions"""
    await interaction.response.defer()

    try:
        embed = await create_ultima_partida_embed(riot_id)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await handle_command_error(interaction, e)

class TeamMemberView(discord.ui.View):
    def __init__(self, aliados):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.aliados = aliados
        
        # Add buttons for each team member (max 5 buttons per row, 25 total)
        for i, jugador in enumerate(aliados[:5]):  # Limit to 5 players max
            player_name = get_player_name(jugador)
            player_riot_id = get_player_riot_id(jugador)
            
            button = discord.ui.Button(
                label=f"{player_name} ({jugador['championName']})",
                style=discord.ButtonStyle.secondary,
                custom_id=f"player_{i}",
                disabled=(player_riot_id is None)  # Disable button if no valid Riot ID
            )
            
            if player_riot_id:
                button.callback = self.create_callback(player_riot_id)
            else:
                # Create a disabled callback that shows an error message
                button.callback = self.create_disabled_callback(player_name)
            
            self.add_item(button)
    
    def create_callback(self, riot_id):
        async def button_callback(interaction):
            # Show the player's last match using our helper function
            await show_player_ultima_partida(interaction, riot_id)
        return button_callback
    
    def create_disabled_callback(self, player_name):
        async def disabled_callback(interaction):
            await interaction.response.send_message(
                f"❌ No se puede obtener información de {player_name} (Riot ID no disponible)",
                ephemeral=True
            )
        return disabled_callback

async def analizar_partida(interaction: discord.Interaction, invocador: str):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(invocador)
        
        participant, match_data, game_duration, game_name, stats, game_mode = await get_match_analysis_data(invocador)
        participants = match_data['info']['participants']
        
        # Get allies (same team as the player)
        player_team = participant['teamId']
        aliados = [p for p in participants if p['teamId'] == player_team]
        
        # Analyze the worst player from the ally team
        peor_nombre, peor_stats, _ = encontrar_peor_jugador(aliados)
        game_mode = match_data["info"].get("gameMode", "Desconocido")
        stats = create_stats_dict(peor_stats, game_duration)
        mensaje = await generar_mensaje_openai(peor_nombre, stats, peor_stats, game_mode)
        
        # Get match result info
        resultado, _ = get_match_result_info(participant)
        
        # Get the worst player's champion for the thumbnail
        peor_champion = peor_stats['championName']
        champion_icon_url = get_champion_icon_url(peor_champion)
        
        # Custom mapping for game mode names
        custom_game_modes = {
            "CLASSIC": "Grieta del Invocador",
            "ARAM": "ARAM", 
            "URF": "Ultra Rapid Fire",
            "CHERRY": "Arena de Noxus"
        }
        game_mode_name = custom_game_modes.get(game_mode, game_mode)
          # Format team stats for embed (truncate if too long)
        resumen_equipo = "\n".join([
            f"• **{get_player_name(p)}** - {p['championName']} (`{format_kda(p)}`)"
            for p in aliados
        ])
        
        # Check if team summary is too long for Discord (max 1024 chars)
        if len(resumen_equipo) > 1000:  # Leave some margin
            # Split into two parts if too long TODO: check bl later
            team_lines = [
                f"• **{get_player_name(p)}** - {p['championName']} (`{format_kda(p)}`)"
                for p in aliados
            ]
            mid_point = len(team_lines) // 2
            resumen_equipo_1 = "\n".join(team_lines[:mid_point])
            resumen_equipo_2 = "\n".join(team_lines[mid_point:])
            split_team = True
        else:
            split_team = False        # Create Discord embed
        embed = discord.Embed(
            title=f"Análisis de partida de {invocador}",
            description=f"🕒 {game_duration} minutos | 🕹️ {resultado}",
            color=0x00ff00 if resultado == "Victoria" else 0xff0000
        )
        
        embed.add_field(
            name=f"Jugador mas vegano: {peor_nombre} ({peor_champion})",
            value=f"Modo de juego: {game_mode_name}",
            inline=False
        )
        
        # Add team field(s) - split if too long
        if split_team:
            embed.add_field(
                name="Equipo (Parte 1):",
                value=resumen_equipo_1,
                inline=False
            )
            embed.add_field(
                name="Equipo (Parte 2):",
                value=resumen_equipo_2,
                inline=False
            )
        else:
            embed.add_field(
                name="Equipo:",
                value=resumen_equipo,
                inline=False
            )
        
        # Truncate analysis message if too long
        if len(mensaje) > 1020:  # Leave margin for formatting
            mensaje = mensaje[:1017] + "..."
        
        embed.add_field(
            name="Análisis del mas mocho:",
            value=mensaje,
            inline=False
        )
        
        embed.set_thumbnail(url=champion_icon_url)
        embed.set_footer(text="CapitanCoditos, Tu afk favorito. • Haz clic en un jugador para ver su última partida.")
        
        # Create view with clickable buttons
        view = TeamMemberView(aliados)
        
        await interaction.followup.send(embed=embed, view=view)
    except Exception as e:
        await handle_command_error(interaction, e)

def register_analizarpartida(tree):
    @app_commands.describe(invocador="Tu nombre de invocador (ej: Roga#LAN)")
    @app_commands.autocomplete(invocador=riot_id_autocomplete)
    @tree.command(name="analizarpartida", description="Analiza tu última partida y encuentra al peor jugador con un resumen divertido.")
    async def command(interaction: discord.Interaction, invocador: str):
        await analizar_partida(interaction, invocador)
