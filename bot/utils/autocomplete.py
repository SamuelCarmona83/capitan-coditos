from discord import app_commands
from utils import api_client


async def riot_id_autocomplete(interaction, current: str):
    try:
        data = await api_client.get("/api/db/summoners/autocomplete", params={"q": current, "limit": 25})
        return [
            app_commands.Choice(name=s, value=s)
            for s in data.get("summoners", [])
        ]
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []
