import discord
from discord import app_commands
from riot.api import get_player_multiple_matches
from utils.helpers import create_match_history_embed, create_ultima_partida_embed, handle_command_error, parse_riot_id, create_stats_dict, get_match_result_info, format_kda, get_summoner_icon_url, is_valid_match_for_analysis
from utils.autocomplete import riot_id_autocomplete
from ai.openai_service import generar_mensaje_openai
from database import save_summoner

class MatchHistoryView(discord.ui.View):
    def __init__(self, riot_id: str, match_results, summoner_profile=None):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.riot_id = riot_id
        self.match_results = match_results
        self.summoner_profile = summoner_profile
        
        # Add buttons for each match (max 5)
        for i, (participant, match_data, game_duration, match_id) in enumerate(match_results[:5]):
            champ = participant["championName"]
            resultado, emoji = get_match_result_info(participant)
            
            button = discord.ui.Button(
                label=f"{emoji} {champ} ({i+1})",
                style=discord.ButtonStyle.success if resultado == "Victoria" else discord.ButtonStyle.danger,
                custom_id=f"match_{i}"
            )
            button.callback = self.create_match_callback(i)
            self.add_item(button)
    
    def create_match_callback(self, match_index):
        async def match_callback(interaction):
            await interaction.response.defer()
            
            try:
                # Get match data for specific match
                participant, match_data, game_duration, match_id = self.match_results[match_index]
                
                # Check if match is valid for analysis
                if not is_valid_match_for_analysis(match_data, participant):
                    # Create simple embed without AI analysis for remake/very short games
                    embed = await create_simple_match_detail_embed(
                        self.riot_id, participant, match_data, game_duration, match_index + 1, self.summoner_profile
                    )
                else:
                    # Create detailed analysis for this specific match
                    game_name = parse_riot_id(self.riot_id)[0]
                    stats = create_stats_dict(participant, game_duration)
                    game_mode = match_data["info"]["gameMode"] or "Desconocido"
                    
                    # Generate AI analysis for this specific match
                    mensaje_openai = await generar_mensaje_openai(game_name, stats, participant, game_mode)
                    
                    # Create detailed embed for this match
                    embed = await create_match_detail_embed(
                        self.riot_id, participant, match_data, game_duration, mensaje_openai, match_index + 1, self.summoner_profile
                    )
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                await handle_command_error(interaction, e)
        
        return match_callback

async def create_simple_match_detail_embed(riot_id: str, participant, match_data, game_duration, match_number: int, summoner_profile=None):
    """Create simple embed for remake/very short matches without AI analysis"""
    from app.utils.helpers import get_champion_icon_url
    
    game_name = parse_riot_id(riot_id)[0]
    
    champ = participant["championName"]
    kda = format_kda(participant)
    resultado, _ = get_match_result_info(participant)
    game_mode = match_data["info"]["gameMode"] or "Desconocido"
    
    # Create champion icon URL
    champion_icon_url = get_champion_icon_url(champ)

    # Custom mapping for game mode names
    custom_game_modes = {
        "CLASSIC": "Grieta del Invocador",
        "ARAM": "ARAM",
        "URF": "Ultra Rapid Fire", 
        "CHERRY": "Arena de Noxus"
    }
    game_mode_name = custom_game_modes.get(game_mode, game_mode)

    # Additional stats
    damage = participant["totalDamageDealtToChampions"]
    gold = participant.get("goldEarned", 0)
    vision_score = participant.get("visionScore", 0)
    cs = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)

    # Create Discord embed
    embed = discord.Embed(
        title=f"Partida #{match_number} - {riot_id}",
        description=f"🎯 **{kda}** | 🕹️ **{resultado}** | 🕒 **{game_duration} min**",
        color=0x00ff00 if resultado == "Victoria" else 0xff0000
    )
    embed.add_field(
        name=f"🏆 {champ} - {game_mode_name}",
        value=f"💰 **{gold:,}** oro | 👁️ **{vision_score}** visión | ⚔️ **{damage:,}** daño | 🗡️ **{cs}** CS",
        inline=False
    )
    
    # Check if it's a very short game (likely remake)
    if game_duration < 5:
        analysis_message = "⚠️ **Partida remake** - Esta partida fue un remake. No se realizó análisis ya que la partida no tuvo desarrollo normal."
    elif game_duration < 8:
        analysis_message = "⏰ **Partida muy corta** - Esta partida terminó muy rápido. No hay suficientes datos para un análisis significativo."
    else:
        analysis_message = "📊 **Partida sin análisis** - No se generó análisis automático para esta partida."
    
    embed.add_field(
        name="🤖 Estado del análisis:",
        value=analysis_message,
        inline=False
    )
    
    embed.set_thumbnail(url=champion_icon_url)
    
    # Set summoner profile icon if available
    if summoner_profile:
        profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
        embed.set_author(name=f"Nivel {summoner_profile['summonerLevel']}", icon_url=profile_icon_url)
    
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    
    return embed

async def create_match_detail_embed(riot_id: str, participant, match_data, game_duration, analysis_message: str, match_number: int, summoner_profile=None):
    """Create detailed embed for a specific match"""
    from utils.helpers import get_champion_icon_url
    
    game_name = parse_riot_id(riot_id)[0]
    
    champ = participant["championName"]
    kda = format_kda(participant)
    resultado, _ = get_match_result_info(participant)
    game_mode = match_data["info"]["gameMode"] or "Desconocido"
    
    # Create champion icon URL
    champion_icon_url = get_champion_icon_url(champ)

    # Custom mapping for game mode names
    custom_game_modes = {
        "CLASSIC": "Grieta del Invocador",
        "ARAM": "ARAM",
        "URF": "Ultra Rapid Fire", 
        "CHERRY": "Arena de Noxus"
    }
    game_mode_name = custom_game_modes.get(game_mode, game_mode)

    # Additional stats
    damage = participant["totalDamageDealtToChampions"]
    gold = participant.get("goldEarned", 0)
    vision_score = participant.get("visionScore", 0)
    cs = participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0)

    # Create Discord embed
    embed = discord.Embed(
        title=f"Partida #{match_number} - {riot_id}",
        description=f"🎯 **{kda}** | 🕹️ **{resultado}** | 🕒 **{game_duration} min**",
        color=0x00ff00 if resultado == "Victoria" else 0xff0000
    )
    embed.add_field(
        name=f"🏆 {champ} - {game_mode_name}",
        value=f"💰 **{gold:,}** oro | 👁️ **{vision_score}** visión | ⚔️ **{damage:,}** daño | 🗡️ **{cs}** CS",
        inline=False
    )
    
    # Truncate analysis message if too long
    if len(analysis_message) > 1020:  # Leave margin for formatting
        analysis_message = analysis_message[:1017] + "..."
    
    embed.add_field(
        name="🤖 Análisis de la partida:",
        value=analysis_message,
        inline=False
    )
    
    embed.set_thumbnail(url=champion_icon_url)
    
    # Set summoner profile icon if available
    if summoner_profile:
        profile_icon_url = get_summoner_icon_url(summoner_profile['profileIconId'])
        embed.set_author(name=f"Nivel {summoner_profile['summonerLevel']}", icon_url=profile_icon_url)
    
    embed.set_footer(text="CapitanCoditos, Tu afk favorito.")
    
    return embed

async def historial_partidas(interaction: discord.Interaction, riot_id: str):
    await interaction.response.defer()

    try:
        # Save summoner to database
        save_summoner(riot_id)
        
        # Get last 5 matches with summoner profile
        match_results, summoner_profile = await get_player_multiple_matches(riot_id, count=5)
        
        if not match_results:
            await interaction.followup.send("❌ No se encontraron partidas recientes para este jugador.")
            return
        
        # Create main embed with match history
        embed = await create_match_history_embed(riot_id, match_results, summoner_profile)
        
        # Create view with clickable buttons
        view = MatchHistoryView(riot_id, match_results, summoner_profile)
        
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        await handle_command_error(interaction, e)

def register_historialpartidas(tree):
    @app_commands.describe(riot_id="Tu Riot ID completo (ej: Roga#LAN)")
    @app_commands.autocomplete(riot_id=riot_id_autocomplete)
    @tree.command(name="historialpartidas", description="Consulta las últimas 5 partidas con análisis detallado de cada una.")
    async def command(interaction: discord.Interaction, riot_id: str):
        await historial_partidas(interaction, riot_id)
