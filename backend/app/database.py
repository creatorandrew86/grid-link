"""SQLite locally; the same rows can be stored through Supabase's REST API."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx

from .models import MarketSettings, Participant, ParticipantInput


DEMO_MEMBERS = [
    {"name": "Solar workshop", "type": "prosumer", "load_kw": 1.2, "solar_kwp": 9},
    {"name": "Florin's home", "type": "prosumer", "load_kw": 0.8, "solar_kwp": 5.5},
    {"name": "Shared rooftop", "type": "prosumer", "load_kw": 1.6, "solar_kwp": 3.6},
    {"name": "Apartment 04", "type": "consumer", "load_kw": 2.4, "solar_kwp": 0},
    {"name": "Corner cafe", "type": "consumer", "load_kw": 4.5, "solar_kwp": 0},
    {"name": "Neighbourhood library", "type": "consumer", "load_kw": 1.8, "solar_kwp": 0},
]


class Database:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if bool(self.url) != bool(self.key):
            raise RuntimeError("Set both SUPABASE_URL and the server-side Supabase key, or neither.")
        self.path = Path(os.getenv("GRIDLINK_DB_PATH", str(Path(__file__).resolve().parents[1] / "data/gridlink.db")))

    @property
    def mode(self):
        return "supabase" if self.url else "local"

    def remote(self, method, table, payload=None, query=""):
        headers = {"apikey": self.key, "Prefer": "return=representation"}
        if self.key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.key}"
        response = httpx.request(method, f"{self.url}/rest/v1/{table}{query}",
                                 headers=headers, json=payload, timeout=10)
        if response.status_code == 409:
            raise ValueError("A member with this name already exists.")
        response.raise_for_status()
        return response.json()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        if self.url:
            self.settings()  # Fail visibly if the migration has not been applied.
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS participants (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    type TEXT NOT NULL, load_kw REAL NOT NULL, solar_kwp REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS market_settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS clearing_events (interval_start TEXT PRIMARY KEY, summary TEXT NOT NULL);
            """)
            fresh = db.execute("SELECT COUNT(*) FROM market_settings").fetchone()[0] == 0
            db.execute("INSERT OR IGNORE INTO market_settings VALUES (1, ?)", (MarketSettings().model_dump_json(),))
            if fresh and os.getenv("GRIDLINK_SEED_DEMO", "1") == "1":
                db.executemany("INSERT INTO participants VALUES (?, ?, ?, ?, ?)",
                               [(str(uuid4()), m["name"], m["type"], m["load_kw"], m["solar_kwp"]) for m in DEMO_MEMBERS])

    def participants(self):
        if self.url:
            rows = self.remote("GET", "participants", query="?select=*&order=name")
        else:
            with self.connect() as db:
                rows = [dict(row) for row in db.execute("SELECT * FROM participants ORDER BY name COLLATE NOCASE")]
        return [Participant.model_validate(row) for row in rows]

    def signup(self, member: ParticipantInput):
        row = {"id": str(uuid4()), **member.model_dump()}
        if self.url:
            return Participant.model_validate(self.remote("POST", "participants", row)[0])
        try:
            with self.connect() as db:
                db.execute("INSERT INTO participants VALUES (?, ?, ?, ?, ?)", tuple(row.values()))
        except sqlite3.IntegrityError as error:
            raise ValueError("A member with this name already exists.") from error
        return Participant(**row)

    def settings(self):
        if self.url:
            return MarketSettings.model_validate(self.remote("GET", "market_settings", query="?id=eq.1&select=value")[0]["value"])
        with self.connect() as db:
            return MarketSettings.model_validate_json(db.execute("SELECT value FROM market_settings WHERE id=1").fetchone()[0])

    def save_settings(self, settings: MarketSettings):
        if self.url:
            self.remote("PATCH", "market_settings", {"value": settings.model_dump()}, "?id=eq.1")
        else:
            with self.connect() as db:
                db.execute("UPDATE market_settings SET value=? WHERE id=1", (settings.model_dump_json(),))

    def save_clearing(self, interval_start, summary):
        if self.url:
            # Ignore a duplicate scheduler retry; the first snapshot for a slot is immutable.
            try:
                return self.remote("POST", "clearing_events", {"interval_start": interval_start, "summary": summary})[0]["summary"]
            except ValueError:
                return self.remote("GET", "clearing_events", query=f"?interval_start=eq.{interval_start}&select=summary")[0]["summary"]
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO clearing_events VALUES (?, ?)", (interval_start, json.dumps(summary)))
            return json.loads(db.execute("SELECT summary FROM clearing_events WHERE interval_start=?", (interval_start,)).fetchone()[0])
