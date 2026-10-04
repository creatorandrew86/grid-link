"""Supabase REST client for GridLink."""
import os
from pathlib import Path
from uuid import uuid4

import httpx

from .models import MarketSettings, Participant


class Database:
    def __init__(self):
        env_file = Path(__file__).resolve().parents[2] / ".env.local"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

        self.url = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", "")).rstrip("/")
        self.key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY", "")
        )

        if not self.url or not self.key:
            raise RuntimeError("Missing Supabase credentials in .env.local.")

        self._community_id = None

    @property
    def mode(self):
        return "supabase"

    @property
    def community_id(self):
        if self._community_id is None:
            try:
                communities = self.remote("GET", "communities", query="?slug=eq.gridlink-community&limit=1")
                if not communities:
                    communities = self.remote("GET", "communities", query="?limit=1")
                if communities:
                    self._community_id = communities[0]["id"]
                else:
                    new_com = self.remote("POST", "communities", {"slug": "default", "name": "GridLink Community"})
                    self._community_id = new_com[0]["id"]
            except Exception:
                self._community_id = None
        return self._community_id

    def remote(self, method: str, table: str, payload=None, query=""):
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Prefer": "return=representation",
            "Content-Type": "application/json",
        }
        res = httpx.request(
            method,
            f"{self.url}/rest/v1/{table}{query}",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if res.status_code == 409:
            raise ValueError("A record with this identifier already exists.")
        res.raise_for_status()
        return res.json()

    def initialize(self):
        self.settings()

    def participants(self):
        cid = self.community_id
        query = f"?community_id=eq.{cid}&select=*&order=name" if cid else "?select=*&order=name"
        rows = self.remote("GET", "participants", query=query)
        return [Participant.model_validate(row) for row in rows]

    def insert_participant(self, row: dict) -> Participant:
        if "id" not in row:
            row["id"] = str(uuid4())
        if self.community_id:
            row["community_id"] = self.community_id
        return Participant.model_validate(self.remote("POST", "participants", row)[0])

    def get_participant_by_email(self, email: str) -> dict | None:
        rows = self.remote("GET", "participants", query=f"?email=eq.{email.strip().lower()}&limit=1")
        return rows[0] if rows else None

    def settings(self):
        cid = self.community_id
        query = f"?community_id=eq.{cid}&select=value&limit=1" if cid else "?select=value&limit=1"
        rows = self.remote("GET", "market_settings", query=query)
        if not rows:
            default = MarketSettings()
            payload = {"community_id": cid, "value": default.model_dump()} if cid else {"id": 1, "value": default.model_dump()}
            self.remote("POST", "market_settings", payload)
            return default
        return MarketSettings.model_validate(rows[0]["value"])

    def save_settings(self, settings: MarketSettings):
        cid = self.community_id
        query = f"?community_id=eq.{cid}" if cid else "?id=eq.1"
        self.remote("PATCH", "market_settings", {"value": settings.model_dump()}, query=query)

    def save_clearing(self, interval_start, summary):
        cid = self.community_id
        payload = {"interval_start": interval_start, "summary": summary}
        if cid:
            payload["community_id"] = cid
            query = f"?community_id=eq.{cid}&interval_start=eq.{interval_start}&select=summary"
        else:
            query = f"?interval_start=eq.{interval_start}&select=summary"
        try:
            return self.remote("POST", "clearing_events", payload)[0]["summary"]
        except Exception:
            return self.remote("GET", "clearing_events", query=query)[0]["summary"]
