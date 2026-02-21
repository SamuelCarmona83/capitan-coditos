"""
MongoDB-backed summoner CRUD (replaces the Postgres summoners.py).
Document shape:
    { _id: "Roga#LAN", game_name: "Roga", tag_line: "LAN",
      search_count: 5, last_searched: ISODate, created_at: ISODate }
"""
from datetime import datetime, timezone
from typing import List

from database.mongo import get_db


def init_database():
    """No-op — indexes are created in mongo.init_mongo()."""
    pass


def save_summoner(riot_id: str, region: str = None, puuid: str = None):
    if "#" not in riot_id:
        return
    game_name, tag_line = riot_id.split("#", 1)
    db = get_db()
    set_fields: dict = {"last_searched": datetime.now(timezone.utc)}
    if region:
        set_fields["region"] = region.upper()
    if puuid:
        set_fields["puuid"] = puuid
    db["summoners"].update_one(
        {"_id": riot_id},
        {
            "$set": set_fields,
            "$inc": {"search_count": 1},
            "$setOnInsert": {
                "_id": riot_id,
                "game_name": game_name,
                "tag_line": tag_line,
                "region": (region.upper() if region else "LAN"),
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


def get_summoners_for_autocomplete(query: str = "", limit: int = 25) -> List[str]:
    db = get_db()
    filter_ = {}
    if query:
        filter_["game_name"] = {"$regex": query, "$options": "i"}

    docs = (
        db["summoners"]
        .find(filter_, {"_id": 1})
        .sort([("search_count", -1), ("last_searched", -1)])
        .limit(limit)
    )
    return [doc["_id"] for doc in docs]


def get_all_summoner_ids() -> List[str]:
    """Return all riot_ids – used by the prefetch worker."""
    db = get_db()
    docs = db["summoners"].find({}, {"_id": 1})
    return [doc["_id"] for doc in docs]


def get_summoners_with_region(limit: int = 200) -> List[tuple]:
    """Return list of (riot_id, region) for all summoners, ordered by recency."""
    db = get_db()
    docs = (
        db["summoners"]
        .find({}, {"_id": 1, "region": 1})
        .sort("last_searched", -1)
        .limit(limit)
    )
    return [(doc["_id"], doc.get("region", "LAN")) for doc in docs]


def get_summoner_stats() -> dict:
    db = get_db()
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_summoners": {"$sum": 1},
                "total_searches": {"$sum": "$search_count"},
            }
        }
    ]
    result = list(db["summoners"].aggregate(pipeline))
    if not result:
        return {"total_summoners": 0, "total_searches": 0}
    row = result[0]
    return {
        "total_summoners": row["total_summoners"],
        "total_searches": row["total_searches"],
    }
