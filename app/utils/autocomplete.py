from discord import app_commands
from database import get_summoners_for_autocomplete

async def riot_id_autocomplete(interaction, current: str):
    """Autocomplete function for riot_id parameters"""
    try:
        # Get matching summoners from database
        summoners = get_summoners_for_autocomplete(current, limit=25)
        
        # Return as autocomplete choices
        return [
            app_commands.Choice(name=summoner, value=summoner)
            for summoner in summoners
        ]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []
