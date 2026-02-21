"""
Pure business-logic helpers (no Discord, no I/O).
Moved from app/utils/helpers.py.
"""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_riot_id(riot_id: str):
    """Parse and validate Riot ID format. Returns (game_name, tag_line)."""
    if "#" not in riot_id:
        raise ValueError("El Riot ID debe tener formato `Nombre#Tag` (ej: Roga#LAN)")
    return riot_id.split("#", 1)


def get_player_name(participant: dict) -> str:
    return (
        participant.get("riotIdGameName")
        or participant.get("summonerName")
        or f"Player_{participant.get('participantId', 'Unknown')}"
    )


def format_kda(participant: dict) -> str:
    return f"{participant['kills']}/{participant['deaths']}/{participant['assists']}"


def get_match_result_info(participant: dict):
    resultado = "Victoria" if participant["win"] else "Derrota"
    emoji = "🏆" if participant["win"] else "💔"
    return resultado, emoji


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_CHAMPION_SPECIAL_CASES = {
    "Wukong": "MonkeyKing",
    "Nunu & Willump": "Nunu",
    "Cho'Gath": "Chogath",
    "Kai'Sa": "Kaisa",
    "Kha'Zix": "Khazix",
    "Kog'Maw": "KogMaw",
    "LeBlanc": "Leblanc",
    "Vel'Koz": "Velkoz",
    "Rek'Sai": "RekSai",
    "Renata Glasc": "Renata",
    "Bel'Veth": "Belveth",
}


def format_champion_name_for_url(champion_name: str) -> str:
    return _CHAMPION_SPECIAL_CASES.get(champion_name, champion_name)


def get_champion_icon_url(champion_name: str, version: str = "15.14.1") -> str:
    return (
        f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/"
        f"{format_champion_name_for_url(champion_name)}.png"
    )


def get_champion_splash_url(champion_name: str, skin_num: int = 0) -> str:
    return (
        f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/"
        f"{format_champion_name_for_url(champion_name)}_{skin_num}.jpg"
    )


def get_summoner_icon_url(profile_icon_id: int, version: str = "15.14.1") -> str:
    return (
        f"https://ddragon.leagueoflegends.com/cdn/{version}/img/profileicon/{profile_icon_id}.png"
    )


# ---------------------------------------------------------------------------
# Match validity
# ---------------------------------------------------------------------------

def is_valid_match_for_analysis(match_data: dict, participant: dict) -> bool:
    duration_min = match_data["info"]["gameDuration"] // 60
    if duration_min < 5:
        return False
    if match_data["info"].get("gameEndedInEarlySurrender", False):
        return False
    damage = participant.get("totalDamageDealtToChampions", 0)
    if (
        damage < 500
        and participant.get("kills", 0) == 0
        and participant.get("deaths", 0) <= 1
        and participant.get("assists", 0) == 0
        and duration_min < 8
    ):
        return False
    return True


# ---------------------------------------------------------------------------
# Stats builder
# ---------------------------------------------------------------------------

def get_farming_info(participant: dict) -> dict:
    role = participant.get("teamPosition", "").upper()
    lane = participant.get("totalMinionsKilled", 0)
    jungle = participant.get("neutralMinionsKilled", 0)
    if role == "JUNGLE":
        return {
            "primary_farm": jungle,
            "primary_farm_type": "monstruos de jungla",
            "secondary_farm": lane,
            "secondary_farm_type": "súbditos de carril",
        }
    return {
        "primary_farm": lane,
        "primary_farm_type": "súbditos de carril",
        "secondary_farm": jungle,
        "secondary_farm_type": "monstruos de jungla",
    }


def get_role_expectations(participant: dict) -> dict:
    role = participant.get("teamPosition", "").upper()
    expectations = {
        "TOP": {"farm_importance": "alta", "farm_target": 150, "vision_importance": "media", "damage_importance": "alta"},
        "MIDDLE": {"farm_importance": "alta", "farm_target": 150, "vision_importance": "media", "damage_importance": "muy_alta"},
        "BOTTOM": {"farm_importance": "muy_alta", "farm_target": 180, "vision_importance": "baja", "damage_importance": "muy_alta"},
        "UTILITY": {"farm_importance": "muy_baja", "farm_target": 30, "vision_importance": "muy_alta", "damage_importance": "baja"},
        "JUNGLE": {"farm_importance": "alta", "farm_target": 120, "vision_importance": "alta", "damage_importance": "alta"},
    }
    return expectations.get(role, expectations["MIDDLE"])


def create_stats_dict(participant: dict, game_duration: int) -> dict:
    farming = get_farming_info(participant)
    role_exp = get_role_expectations(participant)
    kills = participant["kills"]
    deaths = participant["deaths"]
    assists = participant["assists"]
    kda = (kills + assists) / max(1, deaths)
    return {
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": kda,
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "gameDuration": game_duration,
        **farming,
        "role_expectations": role_exp,
        "visionScore": participant.get("visionScore", 0),
        "goldEarned": participant.get("goldEarned", 0),
        "champLevel": participant.get("champLevel", 0),
        "teamPosition": participant.get("teamPosition", "UNKNOWN"),
    }


# ---------------------------------------------------------------------------
# Team analysis
# ---------------------------------------------------------------------------

def encontrar_peor_jugador(participants: list):
    """Return (name, participant_dict, score) for the worst player."""
    def score(p):
        k, d, a = p["kills"], p["deaths"], p["assists"]
        dmg = p["totalDamageDealtToChampions"]
        return (k + a) / max(1, d) + dmg / 10_000

    scores = {get_player_name(p): score(p) for p in participants}
    if not scores:
        return "Unknown", participants[0], 0
    worst_name = min(scores, key=scores.get)
    worst_p = next(p for p in participants if get_player_name(p) == worst_name)
    return worst_name, worst_p, scores[worst_name]


def get_game_mode_label(game_mode: str) -> str:
    mapping = {
        "CLASSIC": "Grieta del Invocador",
        "ARAM": "ARAM",
        "URF": "Ultra Rapid Fire",
        "CHERRY": "Arena de Noxus",
        "ULTBOOK": "Libro de Hechizos",
    }
    return mapping.get(game_mode, game_mode)
