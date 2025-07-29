# file: active_game_notify.py - ENHANCED VERSION WITH EMBED
import asyncio
import discord
import time
import aiohttp
from riot.api import get_summoner_data
from riot.active_game import get_active_game_by_summoner_data
from database.summoners import get_summoners_for_autocomplete

CHECK_INTERVAL = 300  # Check every 5 minutes

CHAMPION_ID_TO_NAME = None  # Will be loaded dynamically

async def fetch_champion_id_to_name():
    """Fetch champion ID to name mapping from Riot Data Dragon dynamically."""
    global CHAMPION_ID_TO_NAME
    if CHAMPION_ID_TO_NAME is not None:
        return CHAMPION_ID_TO_NAME
    
    async with aiohttp.ClientSession() as session:
        # 1. Get latest version
        async with session.get('https://ddragon.leagueoflegends.com/api/versions.json') as resp:
            versions = await resp.json()
            latest_version = versions[0]
        # 2. Get champion data
        url = f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json'
        async with session.get(url) as resp:
            data = await resp.json()
        champ_data = data['data']
        # 3. Build mapping from key (championId as string) to name
        id_to_name = {int(info['key']): info['name'] for info in champ_data.values()}
        CHAMPION_ID_TO_NAME = id_to_name
        return id_to_name

async def get_champion_name_by_id(champion_id):
    """Get champion name from champion ID, fetching dynamically if needed."""
    id_to_name = await fetch_champion_id_to_name()
    return id_to_name.get(champion_id, f"Champion_{champion_id}")

# Queue ID to game mode mapping
QUEUE_ID_TO_MODE = {
    400: "Normal Draft",
    420: "Ranked Solo/Duo",
    430: "Normal Blind",
    440: "Ranked Flex",
    450: "ARAM",
    460: "Normal 3v3",
    470: "Ranked 3v3",
    700: "Clash",
    720: "ARAM",
    800: "Co-op vs AI Intermediate",
    810: "Co-op vs AI Intro",
    820: "Co-op vs AI Beginner",
    830: "Co-op vs AI Intermediate",
    840: "Co-op vs AI Intermediate",
    850: "Co-op vs AI Intermediate",
    900: "URF",
    920: "Poro King",
    1020: "One for All",
    1300: "Nexus Blitz", 
    1400: "Ultimate Spellbook",
    1700: "Arena",
    1900: "URF"
}

def get_game_mode_name(queue_id):
    """Get readable game mode name from queue ID"""
    return QUEUE_ID_TO_MODE.get(queue_id, f"Modo_{queue_id}")

def format_game_duration(game_start_time):
    """Calculate and format game duration from start time"""
    if not game_start_time:
        return "Desconocido"
    
    current_time = int(time.time() * 1000)  # Current time in milliseconds
    duration_ms = current_time - game_start_time
    duration_minutes = duration_ms // (1000 * 60)
    
    if duration_minutes < 1:
        return "Recién iniciada"
    elif duration_minutes < 60:
        return f"{duration_minutes} min"
    else:
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        return f"{hours}h {minutes}min"

async def get_player_active_game_info(active_game, riot_id):
    """Extract player-specific information from active game data (async for dynamic champion fetch)"""
    if not active_game or 'participants' not in active_game:
        return None
    
    game_name, tag_line = riot_id.split('#', 1)
    for participant in active_game['participants']:
        if (participant.get('riotId') == riot_id or 
            participant.get('summonerName', '').lower() == game_name.lower()):
            champion_id = participant.get('championId', 0)
            champion_name = await get_champion_name_by_id(champion_id)
            return {
                'champion_name': champion_name,
                'champion_id': champion_id,
                'summoner_name': participant.get('summonerName', game_name)
            }
    if active_game['participants']:
        participant = active_game['participants'][0]
        champion_id = participant.get('championId', 0)
        champion_name = await get_champion_name_by_id(champion_id)
        return {
            'champion_name': champion_name,
            'champion_id': champion_id,
            'summoner_name': participant.get('summonerName', game_name)
        }
    return None

async def check_bot_permissions(channel):
    """Check bot permissions in the channel and log them"""
    try:
        if hasattr(channel, 'permissions_for'):
            bot_permissions = channel.permissions_for(channel.guild.me)
            
            print(f"[ActiveGameNotify] Bot permissions in #{channel.name}:")
            print(f"  - Send Messages: {bot_permissions.send_messages}")
            print(f"  - Embed Links: {bot_permissions.embed_links}")
            print(f"  - Use External Emojis: {bot_permissions.use_external_emojis}")
            print(f"  - Read Message History: {bot_permissions.read_message_history}")
            
            return bot_permissions.embed_links
        else:
            print(f"[ActiveGameNotify] Cannot check permissions - not a guild channel")
            return False
    except Exception as e:
        print(f"[ActiveGameNotify] Error checking permissions: {e}")
        return False

async def create_active_games_embed(active_players_info):
    """Create a detailed embed for active games notification"""
    if not active_players_info:
        return None
    
    embed = discord.Embed(
        title="🎮 Amigos en partida",
        description=f"**{len(active_players_info)}** amigos están actualmente jugando",
        color=0x00ff9f  # Verde brillante
    )
    
    # Group players by game mode for better organization
    game_modes = {}
    for player_info in active_players_info:
        mode = player_info['game_mode']
        if mode not in game_modes:
            game_modes[mode] = []
        game_modes[mode].append(player_info)
    
    # Add field for each game mode
    for mode, players in game_modes.items():
        player_list = []
        for player in players:
            champion = player['champion_name']
            duration = player['duration']
            riot_id = player['riot_id']
            
            # Truncate riot_id if too long
            display_name = riot_id.split('#')[0] if '#' in riot_id else riot_id
            if len(display_name) > 12:
                display_name = display_name[:12] + "..."
            
            player_list.append(f"**{display_name}** - {champion} ({duration})")
        
        embed.add_field(
            name=f"🎯 {mode}",
            value="\n".join(player_list),
            inline=True
        )
    
    embed.set_footer(text="CapitanCoditos • Información en tiempo real")
    embed.timestamp = discord.utils.utcnow()
    
    return embed

async def check_bot_permissions(channel):
    """Check bot permissions in the channel and log them"""
    try:
        if hasattr(channel, 'permissions_for'):
            bot_permissions = channel.permissions_for(channel.guild.me)
            
            print(f"[ActiveGameNotify] Bot permissions in #{channel.name}:")
            print(f"  - Send Messages: {bot_permissions.send_messages}")
            print(f"  - Embed Links: {bot_permissions.embed_links}")
            print(f"  - Use External Emojis: {bot_permissions.use_external_emojis}")
            print(f"  - Read Message History: {bot_permissions.read_message_history}")
            
            return bot_permissions.embed_links
        else:
            print(f"[ActiveGameNotify] Cannot check permissions - not a guild channel")
            return False
    except Exception as e:
        print(f"[ActiveGameNotify] Error checking permissions: {e}")
        return False

async def notify_active_games_task(bot: discord.Client, channel_id: int = None, user_id: int = None):
    await bot.wait_until_ready()
    target = None
    if channel_id is not None:
        target = bot.get_channel(channel_id)
        if target is None:
            print(f"[ActiveGameNotify] Channel ID {channel_id} not found.")
            return
        # Check and log bot permissions in the channel
        await check_bot_permissions(target)
    elif user_id is not None:
        try:
            target = await bot.fetch_user(user_id)
        except Exception as e:
            print(f"[ActiveGameNotify] User ID {user_id} not found: {e}")
            return
    else:
        print("[ActiveGameNotify] No channel_id or user_id provided.")
        return

    last_active = set()
    consecutive_errors = {}

    while not bot.is_closed():
        try:
            riot_ids = get_summoners_for_autocomplete(limit=100)
            active_now = {}
            print(f"[ActiveGameNotify] === Checking {len(riot_ids)} players ===")
            
            for riot_id in riot_ids:
                try:
                    # Skip players with too many consecutive errors
                    if consecutive_errors.get(riot_id, 0) >= 3:
                        print(f"[ActiveGameNotify] Skipping {riot_id} due to repeated errors")
                        continue
                    
                    print(f"[ActiveGameNotify] Checking {riot_id}")
                    game_name, tag_line = riot_id.split('#', 1)
                    
                    # Get summoner data (this gives us puuid)
                    summoner = get_summoner_data(game_name, tag_line)
                    
                    # Check if we have puuid
                    if 'puuid' not in summoner:
                        print(f"[ActiveGameNotify] Warning: No 'puuid' field for {riot_id}")
                        consecutive_errors[riot_id] = consecutive_errors.get(riot_id, 0) + 1
                        continue
                    
                    # Use the new V5 API method
                    active_game = get_active_game_by_summoner_data(summoner)
                    
                    is_active = bool(active_game)
                    print(f"[ActiveGameNotify] {riot_id} active_game: {is_active}")
                    
                    if is_active and active_game:
                        # Extract detailed game information
                        queue_id = active_game.get('gameQueueConfigId', 0)
                        game_mode = get_game_mode_name(queue_id)
                        game_start_time = active_game.get('gameStartTime', 0)
                        duration = format_game_duration(game_start_time)
                        
                        # Get player-specific info (champion)
                        player_info = await get_player_active_game_info(active_game, riot_id)
                        
                        if player_info:
                            active_now[riot_id] = {
                                'riot_id': riot_id,
                                'champion_name': player_info['champion_name'],
                                'champion_id': player_info['champion_id'],
                                'game_mode': game_mode,
                                'duration': duration,
                                'summoner_name': player_info['summoner_name']
                            }
                        else:
                            # Fallback if we can't get player info
                            active_now[riot_id] = {
                                'riot_id': riot_id,
                                'champion_name': 'Desconocido',
                                'champion_id': 0,
                                'game_mode': game_mode,
                                'duration': duration,
                                'summoner_name': game_name
                            }
                    
                    # Reset error count on success
                    if riot_id in consecutive_errors:
                        del consecutive_errors[riot_id]
                        
                except Exception as ex:
                    print(f"[ActiveGameNotify] Error checking {riot_id}: {ex}")
                    consecutive_errors[riot_id] = consecutive_errors.get(riot_id, 0) + 1
                    continue
              # Calculate changes and send notifications
            current_active_ids = set(active_now.keys())
            new_in_game = current_active_ids - last_active
            finished_games = last_active - current_active_ids
            
            if new_in_game:
                print(f"[ActiveGameNotify] New players in game: {new_in_game}")
                
                # Get detailed info for new players
                new_players_info = [active_now[riot_id] for riot_id in new_in_game]
                
                try:
                    # Try to create and send detailed embed first
                    embed = await create_active_games_embed(new_players_info)
                    
                    if embed:
                        await target.send(embed=embed)
                        print(f"[ActiveGameNotify] Sent detailed embed for {len(new_players_info)} players")
                    else:
                        raise Exception("Embed creation failed")
                        
                except discord.Forbidden:
                    print(f"[ActiveGameNotify] No permission to send embeds, falling back to rich text message")
                    # Create a rich text message with game details
                    message_lines = ["🎮 **Amigos que entraron en partida:**\n"]
                    
                    for player_info in new_players_info:
                        riot_id = player_info['riot_id']
                        champion = player_info['champion_name']
                        game_mode = player_info['game_mode']
                        duration = player_info['duration']
                        
                        # Truncate riot_id if too long
                        display_name = riot_id.split('#')[0] if '#' in riot_id else riot_id
                        if len(display_name) > 12:
                            display_name = display_name[:12] + "..."
                        
                        message_lines.append(f"• **{display_name}** jugando **{champion}** en {game_mode} ({duration})")
                    
                    msg = "\n".join(message_lines)
                    await target.send(msg)
                    
                except Exception as e:
                    print(f"[ActiveGameNotify] Error sending embed notification: {e}")
                    # Final fallback to simple message
                    players_list = ', '.join([f"**{player}**" for player in new_in_game])
                    msg = f'🎮 Amigos que entraron en partida: {players_list}'
                    await target.send(msg)
            
            # Optional: notify when games end
            if finished_games:
                print(f"[ActiveGameNotify] Players finished games: {finished_games}")
                players_list = ', '.join([f"**{player}**" for player in finished_games])
                msg = f'🏁 Amigos que terminaron partida: {players_list}'
                await target.send(msg)
            
            if not new_in_game and not finished_games:
                print(f"[ActiveGameNotify] No changes. Currently active: {len(current_active_ids)}")
            
            # Clean up old errors
            consecutive_errors = {k: v for k, v in consecutive_errors.items() if v < 5}
            
            last_active = current_active_ids
            
            print(f"[ActiveGameNotify] === Cycle complete. Active players: {len(current_active_ids)} ===")
            
        except Exception as e:
            print(f"[ActiveGameNotify] Critical error in main loop: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)