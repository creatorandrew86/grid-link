"""End-to-End Live Integration Test: Switch Bogdan Toma from Community B to Community A using real Supabase DB data."""
import sys
from pathlib import Path
import unittest

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from app.main import create_app
from app.database import Database


class TestLiveCommunitySwitch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Connect directly to the real Supabase database
        cls.db = Database()

        # 2. Query actual communities from the live DB
        communities = cls.db.remote("GET", "communities", query="?select=id,slug,name,battery_policy&order=slug")
        by_slug = {c["slug"]: c for c in communities}

        if "gridlink-community-a" not in by_slug or "gridlink-community-b" not in by_slug:
            raise RuntimeError(
                f"Required communities not found in live DB. Found: {list(by_slug.keys())}. "
                "Please run the setup SQL query in Supabase first."
            )

        cls.comm_a = by_slug["gridlink-community-a"]
        cls.comm_b = by_slug["gridlink-community-b"]

        # 3. Initialize real FastAPI client
        cls.client = TestClient(create_app())

    def setUp(self):
        # Ensure starting state in live DB: Bogdan is in Community B and eligible for Community A
        self.db.remote(
            "PATCH",
            "participants",
            {"community_id": self.comm_b["id"], "battery_interested": True},
            query="?email=eq.btoma0513@gmail.com"
        )
        self.db.remote(
            "PATCH",
            "approved_pods",
            {
                "community_id": self.comm_b["id"],
                "battery_eligible_communities": [self.comm_a["id"]]
            },
            query="?pod=eq.RO001BOGDANTOMA01"
        )

    def test_switch_bogdan_from_b_to_a_in_live_db(self):
        print("\n" + "=" * 70)
        print(" LIVE SUPABASE DATABASE INTEGRATION TEST")
        print(" Moving user 'Bogdan Toma' from Community B -> Community A")
        print("=" * 70)

        # 1. Authenticate via real login endpoint
        login_resp = self.client.post("/api/login", json={
            "email": "btoma0513@gmail.com",
            "password": "password123"
        })
        self.assertEqual(login_resp.status_code, 200, f"Login failed: {login_resp.text}")
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Check current profile from live DB
        me_before = self.client.get("/api/me", headers=headers).json()
        print(f"\n1. [BEFORE SWITCH] User: {me_before['name']} ({me_before['email']})")
        print(f"   -> Current Community: {self.comm_b['name']}")
        print(f"   -> Community ID:      {me_before['community_id']}")
        self.assertEqual(me_before["community_id"], self.comm_b["id"])

        # 3. Check community battery suggestions
        battery_ctx = self.client.get("/api/community-battery", headers=headers).json()
        candidates = battery_ctx.get("candidates", [])
        candidate_ids = [c["id"] for c in candidates]
        print(f"\n2. [ELIGIBLE CANDIDATES FOUND]: {len(candidates)}")
        for c in candidates:
            print(f"   -> {c['name']} (ID: {c['id']}, Policy: {c['battery_policy']})")
        self.assertIn(self.comm_a["id"], candidate_ids)

        # 4. TRIGGER THE SWITCH: POST /api/community-battery/switch
        print(f"\n3. [TRIGGERING SWITCH]: Sending POST /api/community-battery/switch...")
        print(f"   -> Target Community: {self.comm_a['name']} ({self.comm_a['id']})")
        switch_resp = self.client.post(
            "/api/community-battery/switch",
            headers=headers,
            json={"target_community_id": self.comm_a["id"]}
        )
        self.assertEqual(switch_resp.status_code, 200, f"Switch failed: {switch_resp.text}")
        transfer_result = switch_resp.json()["transfer"]
        print(f"   -> Result from Postgres transfer function: {transfer_result}")
        self.assertEqual(transfer_result["status"], "accepted")

        # 5. Verify the profile endpoint now reflects Community A
        me_after = self.client.get("/api/me", headers=headers).json()
        print(f"\n4. [AFTER SWITCH] User: {me_after['name']} ({me_after['email']})")
        print(f"   -> New Community:     {self.comm_a['name']}")
        print(f"   -> Community ID:      {me_after['community_id']}")
        self.assertEqual(me_after["community_id"], self.comm_a["id"])

        # 6. Verify directly in the live Supabase database tables
        db_participant = self.db.get_participant_by_email("btoma0513@gmail.com")
        self.assertEqual(db_participant["community_id"], self.comm_a["id"])

        db_pod = self.db.remote("GET", "approved_pods", query="?pod=eq.RO001BOGDANTOMA01&limit=1")[0]
        self.assertEqual(db_pod["community_id"], self.comm_a["id"])

        print("\n5. [DATABASE VERIFICATION]:")
        print(f"   -> public.participants.community_id in DB:  {db_participant['community_id']} (Matches Community A)")
        print(f"   -> public.approved_pods.community_id in DB: {db_pod['community_id']} (Matches Community A)")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    unittest.main()
