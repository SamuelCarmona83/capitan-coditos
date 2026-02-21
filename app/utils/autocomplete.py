import asyncio
from discord import app_commands
from database import get_summoners_with_region

async def riot_id_autocomplete(interaction, current: str):
    """Autocomplete function for riot_id parameters, shows stored region as hint."""
    try:
        # Fetch all (riot_id, region) pairs, filter in-process so we can match by name
        all_summoners = await asyncio.to_thread(get_summoners_with_region, 100)

        # Filter by current input (case-insensitive match on game name part)
        current_lower = current.lower()
        matches = [
            (riot_id, region)
            for riot_id, region in all_summoners
            if current_lower in riot_id.lower()
        ][:25]

        # Display includes region so the user can tell accounts apart
        return [
            app_commands.Choice(
                name=f"{riot_id}  [{region}]",
                value=riot_id,
            )
            for riot_id, region in matches
        ]
    except Exception as e:
        print(f"Error in autocomplete: {e}")
        return []
