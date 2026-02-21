"""Active game notifier — polls Flask API instead of Riot directly."""
import asyncio
import time

import aiohttp
import discord

from utils import api_client

CHECK_INTERVAL = 300  # seconds between cycles
DEFAULT_REGION = "LAN"

CHAMPION_ID_TO_NAME: dict | None = None


async def _fetch_champion_id_to_name() -> dict:
    global CHAMPION_ID_TO_NAME
    if CHAMPION_ID_TO_NAME is not None:
        return CHAMPION_ID_TO_NAME
    async with aiohttp.ClientSession() as session:
        async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as r:
            versions = await r.json()
        url = f"https://ddragon.leagueoflegends.com/cdn/{versions[0]}/data/en_US/champion.json"
        async with session.get(url) as r:
            data = await r.json()
    CHAMPION_ID_TO_NAME = {int(v["key"]): v["name"] for v in data["data"].values()}
    return CHAMPION_ID_TO_NAME


async def _get_champion_name(champion_id: int) -> str:
    mapping = await _fetch_champion_id_to_name()
    return mapping.get(champion_id, f"Champion_{champion_id}")


QUEUE_ID_TO_MODE = {
    400: "Normal Draft",  420: "Ranked Solo/Duo",  430: "Normal Blind",
    440: "Ranked Flex",   450: "ARAM",              700: "Clash",
    900: "URF",           1020: "One for All",      1300: "Nexus Blitz",
    1400: "Ultimate Spellbook", 1700: "Arena", 1900: "URF",
}


def _game_mode_name(queue_id: int) -> str:
    return QUEUE_ID_TO_MODE.get(queue_id, f"Modo_{queue_id}")


def _format_duration(game_start_ms: int) -> str:
    if not game_start_ms:
        return "Desconocida"
    minutes = (int(time.time() * 1000) - game_start_ms) // 60000
    if minutes < 1:
        return "Recién iniciada"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h {minutes % 60}min"


async def _player_info_from_game(game_data: dict, riot_id: str) -> dict:
    """Extract the tracked player's participant entry from the raw active-game dict."""
    game_name = riot_id.split("#")[0]
    for p in game_data.get("participants", []):
        if p.get("riotId") == riot_id or p.get("summonerName", "").lower() == game_name.lower():
            champ_id = p.get("championId", 0)
            return {"champion_name": await _get_champion_name(champ_id), "champion_id": champ_id}
    # Fallback: first participant
    p0 = game_data["participants"][0] if game_data.get("participants") else {}
    champ_id = p0.get("championId", 0)
    return {"champion_name": await _get_champion_name(champ_id), "champion_id": champ_id}


async def _create_embed(active_players: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title="🎮 Amigos en partida",
        description=f"**{len(active_players)}** amigos están actualmente jugando",
        color=0x00FF9F,
    )
    # Group by game mode
    by_mode: dict[str, list] = {}
    for p in active_players:
        by_mode.setdefault(p["game_mode"], []).append(p)
    for mode, players in by_mode.items():
        lines = []
        for pl in players:
            name = pl["riot_id"].split("#")[0]
            if len(name) > 12:
                name = name[:12] + "…"
            lines.append(f"**{name}** — {pl['champion_name']} ({pl['duration']})")
        embed.add_field(name=f"🎯 {mode}", value="\n".join(lines), inline=True)
    embed.set_footer(text="CapitanCoditos • Información en tiempo real")
    embed.timestamp = discord.utils.utcnow()
    return embed


async def notify_active_games_task(
    bot: discord.Client,
    channel_id: int | None = None,
    user_id: int | None = None,
    region: str = DEFAULT_REGION,
):
    await bot.wait_until_ready()

    # Resolve notification target
    if channel_id is not None:
        target = bot.get_channel(channel_id)
        if target is None:
            print(f"[ActiveGameNotify] Channel {channel_id} not found.")
            return
    elif user_id is not None:
        try:
            target = await bot.fetch_user(user_id)
        except Exception as e:
            print(f"[ActiveGameNotify] User {user_id} not found: {e}")
            return
    else:
        print("[ActiveGameNotify] No channel_id or user_id provided.")
        return

    last_active: set[str] = set()
    consecutive_errors: dict[str, int] = {}

    while not bot.is_closed():
        try:
            # Fetch summoner list with per-summoner region from API
            resp = await api_client.get("/api/db/summoners/with-region", params={"limit": 200})
            summoner_list = resp.get("summoners", [])  # [{riot_id, region}, ...]

            print(f"[ActiveGameNotify] Checking {len(summoner_list)} players")
            active_now: dict[str, dict] = {}

            for entry in summoner_list:
                riot_id = entry["riot_id"]
                summoner_region = entry.get("region", "LAN")
                if not riot_id:
                    continue
                if consecutive_errors.get(riot_id, 0) >= 3:
                    continue
                try:
                    resp = await api_client.get(
                        f"/api/summoner/{riot_id}/active-game",
                        params={"region": summoner_region},
                    )
                    if resp.get("in_game") and resp.get("game_data"):
                        game_data = resp["game_data"]
                        queue_id = game_data.get("gameQueueConfigId", 0)
                        p_info = await _player_info_from_game(game_data, riot_id)
                        active_now[riot_id] = {
                            "riot_id": riot_id,
                            "champion_name": p_info["champion_name"],
                            "champion_id": p_info["champion_id"],
                            "game_mode": _game_mode_name(queue_id),
                            "duration": _format_duration(game_data.get("gameStartTime", 0)),
                        }
                    consecutive_errors.pop(riot_id, None)
                except Exception as ex:
                    print(f"[ActiveGameNotify] Error checking {riot_id}: {ex}")
                    consecutive_errors[riot_id] = consecutive_errors.get(riot_id, 0) + 1
            current_ids = set(active_now)
            new_in_game = current_ids - last_active
            finished = last_active - current_ids

            if new_in_game:
                print(f"[ActiveGameNotify] New in game: {new_in_game}")
                try:
                    embed = await _create_embed([active_now[r] for r in new_in_game])
                    await target.send(embed=embed)
                except discord.Forbidden:
                    lines = ["🎮 **Amigos que entraron en partida:**\n"]
                    for r in new_in_game:
                        p = active_now[r]
                        name = r.split("#")[0][:12]
                        lines.append(f"• **{name}** jugando **{p['champion_name']}** en {p['game_mode']}")
                    await target.send("\n".join(lines))
                except Exception as e:
                    print(f"[ActiveGameNotify] Embed send error: {e}")
                    await target.send(f"🎮 Amigos en partida: {', '.join(new_in_game)}")

            if finished:
                print(f"[ActiveGameNotify] Finished: {finished}")
                await target.send(f"🏁 Amigos que terminaron partida: {', '.join(f'**{r}**' for r in finished)}")

            if not new_in_game and not finished:
                print(f"[ActiveGameNotify] No changes. Active: {len(current_ids)}")

            consecutive_errors = {k: v for k, v in consecutive_errors.items() if v < 5}
            last_active = current_ids

        except Exception as e:
            print(f"[ActiveGameNotify] Critical error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)
