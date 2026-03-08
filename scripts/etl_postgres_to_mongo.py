"""
ETL: Postgres / SQLite → MongoDB

Reads all rows from the `summoners` table in the existing Postgres (or SQLite)
database and upserts them into the MongoDB `summoners` collection.

Usage:
    # Against Postgres
    POSTGRES_URL=postgresql://user:pass@host:5432/discbot \
    MONGO_URL=mongodb://localhost:27017 \
    python scripts/etl_postgres_to_mongo.py

    # Against SQLite fallback (no POSTGRES_URL)
    MONGO_URL=mongodb://localhost:27017 \
    python scripts/etl_postgres_to_mongo.py
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Source: Postgres or SQLite
# ---------------------------------------------------------------------------

POSTGRES_URL = os.getenv("POSTGRES_URL")
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "database", "summoners.db")


def _read_summoners_postgres() -> list[dict]:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(POSTGRES_URL, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT riot_id, game_name, tag_line,
                       COALESCE(search_count, 0)  AS search_count,
                       last_searched, created_at
                FROM   summoners
                """
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _read_summoners_sqlite() -> list[dict]:
    if not os.path.exists(SQLITE_PATH):
        print(f"[ETL] SQLite file not found at {SQLITE_PATH}")
        return []
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT riot_id, game_name, tag_line,
                   COALESCE(search_count, 0) AS search_count,
                   last_searched, created_at
            FROM   summoners
            """
        )
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError as e:
        print(f"[ETL] SQLite read error: {e}")
        return []
    finally:
        conn.close()


def read_source_summoners() -> list[dict]:
    if POSTGRES_URL:
        print("[ETL] Reading from PostgreSQL …")
        try:
            rows = _read_summoners_postgres()
            print(f"[ETL] Found {len(rows)} rows in Postgres.")
            return rows
        except Exception as e:
            print(f"[ETL] Postgres error: {e}. Trying SQLite …")
    print("[ETL] Reading from SQLite …")
    rows = _read_summoners_sqlite()
    print(f"[ETL] Found {len(rows)} rows in SQLite.")
    return rows


# ---------------------------------------------------------------------------
# Target: MongoDB
# ---------------------------------------------------------------------------

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "capitancoditos")


def _coerce_dt(value) -> datetime | None:
    """Normalise various timestamp representations to a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                dt = datetime.strptime(value.split("+")[0].rstrip("Z"), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def upsert_to_mongo(rows: list[dict]) -> None:
    from pymongo import MongoClient, UpdateOne

    client = MongoClient(MONGO_URL)
    db = client[MONGO_DB]
    collection = db["summoners"]

    # Ensure index
    collection.create_index("search_count")

    ops = []
    for row in rows:
        riot_id = row.get("riot_id")
        if not riot_id:
            print(f"[ETL] Skipping row with missing riot_id: {row}")
            continue

        # Parse riot_id into components if game_name/tag_line are missing
        game_name = row.get("game_name") or ""
        tag_line = row.get("tag_line") or ""
        if not game_name and "#" in riot_id:
            game_name, tag_line = riot_id.split("#", 1)

        doc = {
            "game_name": game_name,
            "tag_line": tag_line,
            "search_count": int(row.get("search_count") or 0),
            "last_searched": _coerce_dt(row.get("last_searched")),
            "created_at": _coerce_dt(row.get("created_at")) or datetime.now(tz=timezone.utc),
        }
        ops.append(UpdateOne({"_id": riot_id}, {"$set": doc}, upsert=True))

    if not ops:
        print("[ETL] No operations to execute.")
        return

    result = collection.bulk_write(ops, ordered=False)
    print(
        f"[ETL] Done — upserted: {result.upserted_count}, "
        f"modified: {result.modified_count}, "
        f"total ops: {len(ops)}"
    )
    client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    rows = read_source_summoners()
    if not rows:
        print("[ETL] Nothing to migrate. Exiting.")
        sys.exit(0)

    print(f"\n[ETL] Migrating {len(rows)} summoners to MongoDB ({MONGO_URL}/{MONGO_DB}) …\n")
    upsert_to_mongo(rows)
    print("\n[ETL] Migration complete. ✅")
    print("[ETL] You can now drop the Postgres `summoners` table and remove the `db` service from docker-compose.")


if __name__ == "__main__":
    main()
