"""Test and demonstration script for switching a user between communities."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

# Ensure 'backend' directory is in python search path
sys.path.insert(0, str(Path(__file__).resolve().parent))

with patch("app.database.Database.__init__", return_value=None):
    from app.main import create_app
from fastapi.testclient import TestClient
from app.sign_up import hash_password
from app.models import Participant, MarketSettings

COMMUNITY_A_ID = "11111111-1111-1111-1111-111111111111"
COMMUNITY_B_ID = "22222222-2222-2222-2222-222222222222"
USER_ID = "00000000-0000-0000-0000-000000000001"


class TestUserCommunitySwitch(unittest.TestCase):
    def setUp(self):
        # 1. Initial user state: belongs to Community A
        self.user_record = {
            "id": USER_ID,
            "community_id": COMMUNITY_A_ID,
            "name": "Bogdan Toma",
            "email": "btoma0513@gmail.com",
            "password_hash": hash_password("secret123"),
            "pod": "RO001BOGDANTOMA01",
            "type": "prosumer",
            "load_kw": 3.5,
            "solar_kwp": 6.0,
        }

        # 2. Mock database layer to isolate the test from network dependencies
        with patch("app.main.Database", autospec=True) as mock_db_class:
            self.mock_db = mock_db_class.return_value
            self.mock_db.mode = "test"
            self.mock_db.get_participant_by_email.return_value = self.user_record

            # Return current user record on SELECT from participants
            self.mock_db.remote.side_effect = lambda method, table, query="", **kwargs: [self.user_record]

            # Return community metadata for source and destination
            self.mock_db.community_details.side_effect = lambda cid: {
                "id": cid,
                "name": "GridLink Base" if cid == COMMUNITY_A_ID else "GridLink Solar & Storage",
                "timezone": "Europe/Bucharest",
                "network_zone": "RO-B-01",
                "battery_meter_boundary": "shared_meter",
                "battery_policy": "approved",
            }

            self.mock_db.participants.return_value = [Participant.model_validate(self.user_record)]
            self.mock_db.settings.return_value = MarketSettings()
            self.mock_db.battery_interests.return_value = []
            self.mock_db.measured_history.return_value = []

            # Community B is an eligible candidate for this user's POD
            self.mock_db.battery_candidates.return_value = [
                {"id": COMMUNITY_B_ID, "name": "GridLink Solar & Storage", "battery_policy": "approved"}
            ]

            # Simulate the accept_battery_transfer RPC updating the database record
            def fake_transfer(participant_id, target_id):
                self.user_record["community_id"] = target_id
                return {"id": "transfer-uuid-12345", "status": "accepted", "community_id": target_id}

            self.mock_db.accept_battery_transfer.side_effect = fake_transfer

            # Initialize FastAPI application test client
            self.client = TestClient(create_app())

    def test_automatic_community_switch_flow(self):
        print("\n" + "=" * 65)
        print(" DEMO: Triggering community switch for user")
        print("=" * 65)

        # Step 1: User logs in and receives session token
        login_resp = self.client.post("/api/login", json={
            "email": "btoma0513@gmail.com",
            "password": "secret123"
        })
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Verify user is initially in Community A
        me_before = self.client.get("/api/me", headers=headers).json()
        print(f"1. [BEFORE TRIGGER] User '{me_before['name']}' is in Community:")
        print(f"   -> community_id: {me_before['community_id']} (Community A)")
        self.assertEqual(me_before["community_id"], COMMUNITY_A_ID)

        # Step 3: Verify candidate destination is available
        battery_ctx = self.client.get("/api/community-battery", headers=headers).json()
        candidate_ids = [c["id"] for c in battery_ctx["candidates"]]
        self.assertIn(COMMUNITY_B_ID, candidate_ids)
        print(f"2. [CANDIDATE DISCOVERED] Eligible target found: {COMMUNITY_B_ID}")

        # Step 4: TRIGGER THE SWITCH!
        # Calling this endpoint initiates the transfer function and updates the user
        print(f"3. [TRIGGERING SWITCH] Calling POST /api/community-battery/switch...")
        switch_resp = self.client.post(
            "/api/community-battery/switch",
            headers=headers,
            json={"target_community_id": COMMUNITY_B_ID}
        )
        self.assertEqual(switch_resp.status_code, 200)
        print(f"   -> Transfer response status: '{switch_resp.json()['transfer']['status']}'")

        # Step 5: Verify user has automatically switched to Community B
        me_after = self.client.get("/api/me", headers=headers).json()
        print(f"4. [AFTER TRIGGER] User '{me_after['name']}' is now in Community:")
        print(f"   -> community_id: {me_after['community_id']} (Community B)")
        print("=" * 65 + "\n")

        self.assertEqual(me_after["community_id"], COMMUNITY_B_ID)
        self.assertEqual(switch_resp.json()["user"]["community_id"], COMMUNITY_B_ID)


if __name__ == "__main__":
    unittest.main()
