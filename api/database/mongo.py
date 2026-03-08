from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection

_client: MongoClient = None
_db = None


def init_mongo(mongo_url: str, db_name: str):
    global _client, _db
    _client = MongoClient(mongo_url)
    _db = _client[db_name]

    # Ensure indexes
    summoners: Collection = _db["summoners"]
    summoners.create_index("search_count", background=True)

    matches: Collection = _db["matches"]
    # _id is matchId – already unique by default

    profiles: Collection = _db["summoner_profiles"]
    # _id is riot_id – already unique by default
    # TTL index on updated_at – expire documents after 24 h (86400 s)
    profiles.create_index("updated_at", expireAfterSeconds=86400, background=True)


def get_db():
    if _db is None:
        raise RuntimeError("MongoDB has not been initialized. Call init_mongo() first.")
    return _db
