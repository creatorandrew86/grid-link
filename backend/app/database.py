"""Supabase REST client for GridLink."""
import os
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
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
        try:
            self.settings()
        except Exception:
            pass

    def participants(self, community_id=None):
        cid = community_id or self.community_id
        query = f"?community_id=eq.{cid}&select=*&order=name" if cid else "?select=*&order=name"
        rows = self.remote("GET", "participants", query=query)
        return [Participant.model_validate(row) for row in rows]

    def insert_participant(self, row: dict) -> Participant:
        if "id" not in row:
            row["id"] = str(uuid4())
        if not row.get("community_id") and self.community_id:
            row["community_id"] = self.community_id
        return Participant.model_validate(self.remote("POST", "participants", row)[0])

    def get_participant_by_email(self, email: str) -> dict | None:
        rows = self.remote("GET", "participants", query=f"?email=eq.{email.strip().lower()}&limit=1")
        return rows[0] if rows else None

    def settings(self, community_id=None):
        cid = community_id or self.community_id
        query = f"?community_id=eq.{cid}&select=value&limit=1" if cid else "?select=value&limit=1"
        rows = self.remote("GET", "market_settings", query=query)
        if not rows:
            default = MarketSettings()
            payload = {"community_id": cid, "value": default.model_dump()} if cid else {"id": 1, "value": default.model_dump()}
            self.remote("POST", "market_settings", payload)
            return default
        return MarketSettings.model_validate(rows[0]["value"])

    def community_details(self, community_id):
        rows = self.remote("GET", "communities", query=f"?id=eq.{community_id}&limit=1")
        if not rows:
            raise ValueError("Community not found.")
        row = rows[0]
        # Demo-only metadata uses the existing description column; no deployment migration required.
        try:
            demo = json.loads(row.get("description") or "")
            if isinstance(demo, dict) and demo.get("gridlink_demo") is True:
                row = {**row, "is_demo": True, "battery_analysis_config": demo["battery_analysis_config"]}
        except (ValueError, KeyError):
            pass
        return row

    def demo_history(self, community_id):
        """Replay fixtures stay outside real meter history and follow the hypothetical demo roster."""
        ids = {p.id for p in self.participants(community_id)}
        rows = self.remote("GET", "clearing_events", query=(
            f"?community_id=eq.{community_id}&summary->>mode=eq.demo_battery"
            "&select=interval_start,summary&order=interval_start&limit=1000"))
        result = []
        for row in rows:
            summary = row["summary"]
            profiles = summary.get("demo_member_profiles", {})
            if not ids <= set(profiles):
                continue
            loads = {pid: profiles[pid]["load_kwh"] for pid in ids}
            solar = {pid: profiles[pid]["generation_kwh"] for pid in ids}
            result.append({"interval_start": row["interval_start"], "summary": {
                **summary, "measurement": {**summary["measurement"], "load_kwh": sum(loads.values()),
                    "generation_kwh": sum(solar.values()), "member_loads_kwh": loads,
                    "member_generation_kwh": solar}}})
        return result

    def battery_interests(self, community_id):
        return self.remote("GET", "community_battery_interest",
                           query=f"?community_id=eq.{community_id}&select=participant_id,interested")

    def save_battery_interest(self, member, interested):
        # Keep one preference per member, including after a transfer.
        table = "community_battery_interest"
        rows = self.remote("GET", table, query=f"?participant_id=eq.{member['id']}&limit=1")
        payload = {"participant_id": member["id"], "community_id": member["community_id"],
                   "interested": interested, "updated_at": datetime.now(timezone.utc).isoformat()}
        return self.remote("PATCH" if rows else "POST", table, payload,
                           query=f"?participant_id=eq.{member['id']}" if rows else "")[0]

    def battery_candidates(self, community, member):
        zone = community.get("network_zone")
        if not zone:
            return []
        approvals = self.remote("GET", "approved_pods", query=(
            f"?pod=eq.{quote(member['pod'], safe='')}&community_id=eq.{community['id']}"
            "&is_active=eq.true&select=battery_eligible_communities&limit=1"))
        allowed = set(approvals[0].get("battery_eligible_communities", [])) if approvals else set()
        if not allowed:
            return []
        candidates = self.remote("GET", "communities", query=(
            f"?id=neq.{community['id']}&network_zone=eq.{quote(zone, safe='')}"
            "&battery_policy=in.(interested,approved)&battery_accepting_members=eq.true"
            "&battery_meter_boundary=eq.shared_meter&select=id,name,battery_policy&order=battery_policy,name"))
        return [c for c in candidates if c["id"] in allowed]

    def accept_battery_transfer(self, participant_id, target_id):
        return self.remote("POST", "rpc/accept_battery_community_transfer", {
            "p_participant_id": participant_id, "p_target_id": target_id})

    def measured_history(self, community_id):
        # ponytail: replay the last 120 days; paginate a longer archive for seasonal studies.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        rows, offset = [], 0
        while True:
            page = self.remote("GET", "community_meter_intervals", query=(
                f"?community_id=eq.{community_id}&interval_start=gte.{quote(cutoff, safe='')}"
                f"&select=interval_start,summary&order=interval_start&limit=1000&offset={offset}"))
            rows.extend(page)
            if len(page) < 1000:
                return rows
            offset += len(page)

    def save_measurements(self, batch):
        payload = [{"community_id": str(batch.community_id), "interval_start": r.interval_start.isoformat(),
                    "summary": {"mode": "measured", "currency": "RON", "meter_boundary": "shared_meter",
                                "battery_free_baseline": True, "interval_minutes": r.interval_minutes,
                                "measurement": r.model_dump(mode="json", exclude={"interval_start", "interval_minutes"})}}
                   for r in batch.readings]
        return self.remote("POST", "community_meter_intervals", payload)

    def save_settings(self, settings: MarketSettings, community_id=None):
        cid = community_id or self.community_id
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
