import json
import sqlite3
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prozorro_history.normalize import Lot

SCHEMA = """
    CREATE TABLE IF NOT EXISTS lots(
        procedure_id TEXT PRIMARY KEY,
        auction_id TEXT NOT NULL UNIQUE,
        previous_auction_id TEXT,
        tender_attempts INTEGER,
        status TEXT,
        selling_method TEXT,
        date_modified TEXT,
        title TEXT,
        start_price REAL,
        currency TEXT,
        cav_code TEXT,
        region TEXT,
        locality TEXT,
        area_m2 REAL,
        land_area_ha REAL,
        auction_date TEXT,
        source_url TEXT NOT NULL,
        api_url TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_lots_previous ON lots(previous_auction_id);

    CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


LOT_COLUMNS = [f.name for f in fields(Lot)]
ALL_COLUMNS = LOT_COLUMNS + ["raw_json", "first_seen", "last_seen"]
UPDATE_COLUMNS = [
    c for c in ALL_COLUMNS if c not in {"procedure_id", "first_seen", "last_seen"}
]

COLUMN_LIST = ", ".join(ALL_COLUMNS)
PLACEHOLDERS = ", ".join(f":{c}" for c in ALL_COLUMNS)
UPDATE_LIST = ", ".join(f"{c} = excluded.{c}" for c in UPDATE_COLUMNS)

UPSERT_SQL = f"""
    INSERT INTO lots ({COLUMN_LIST}) VALUES ({PLACEHOLDERS})
    ON CONFLICT(procedure_id) DO UPDATE SET {UPDATE_LIST}
    WHERE excluded.date_modified > lots.date_modified
"""


def upsert_lot(conn: sqlite3.Connection, lot: Lot, raw: dict[str, Any]) -> bool:
    now = datetime.now(UTC).isoformat()
    params = asdict(lot)
    params["raw_json"] = json.dumps(raw)
    params["first_seen"] = now
    params["last_seen"] = now

    cur = conn.execute(UPSERT_SQL, params)
    changed = cur.rowcount > 0
    conn.execute(
        "UPDATE lots SET last_seen = ? WHERE procedure_id = ?",
        (now, lot.procedure_id),
    )
    return changed


def get_lot(conn: sqlite3.Connection, auction_id: str) -> Lot | None:
    row = conn.execute(
        "SELECT * FROM lots WHERE auction_id = ?", (auction_id,)
    ).fetchone()
    if row is None:
        return None
    return Lot(**{c: row[c] for c in LOT_COLUMNS})


def get_cursor(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT value FROM state WHERE key = 'cursor'").fetchone()
    if row is None:
        return None
    value: str | None = row["value"]
    return value


def set_cursor(conn: sqlite3.Connection, value: str) -> None:
    conn.execute(
        "INSERT INTO state (key, value) VALUES ('cursor', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (value,),
    )
