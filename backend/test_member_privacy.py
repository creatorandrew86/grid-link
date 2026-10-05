"""Run with: python -m unittest discover -s backend -p test_member_privacy.py -v"""
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models import MarketSettings, Participant
from app.sign_up import hash_password

with patch("app.database.Database.__init__", return_value=None):
    from app.main import create_app


class MemberPrivacyChecks(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"id": "alice", "name": "Alice", "type": "consumer", "load_kw": 2,
             "solar_kwp": 0, "email": "alice@example.com", "pod": "PRIVATEALICE"},
            {"id": "bob", "name": "Bob", "type": "prosumer", "load_kw": 1,
             "solar_kwp": 5, "email": "bob@example.com", "pod": "PRIVATEBOB"},
        ]
        password_hash = hash_password("correct-password")
        with patch("app.main.Database", autospec=True) as factory:
            db = factory.return_value
            db.mode = "test"
            db.participants.return_value = [Participant(**row) for row in self.rows]
            db.settings.return_value = MarketSettings()
            db.get_participant_by_email.side_effect = lambda email: next(
                ({**row, "password_hash": password_hash} for row in self.rows if row["email"] == email), None)
            db.remote.side_effect = lambda method, table, query: [
                {**row, "password_hash": password_hash} for row in self.rows
                if query == f"?id=eq.{row['id']}&limit=1"]
            self.client = TestClient(create_app())

    def login(self, name="alice"):
        response = self.client.post("/api/login", json={
            "email": f"{name}@example.com", "password": "correct-password"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("password_hash", response.json()["user"])
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_visitors_get_only_community_totals(self):
        response = self.client.get("/api/clearing-summary")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["participants"], [])
        self.assertEqual(result["participant_count"], 2)
        self.assertGreater(result["totals"]["load_kwh"], 0)
        self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(self.client.get("/api/community").json(), {"participant_count": 2, "storage": "test"})
        self.assertEqual(self.client.post("/api/clearing-preview", json={}).json()["participants"], [])
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_each_member_gets_only_their_own_bill_and_profile(self):
        public_totals = self.client.get("/api/clearing-summary").json()["totals"]
        for name in ("alice", "bob"):
            headers = self.login(name)
            result = self.client.get("/api/clearing-summary", headers=headers).json()
            self.assertEqual([row["id"] for row in result["participants"]], [name])
            self.assertEqual(result["totals"], public_totals)
            self.assertEqual(result["participant_count"], 2)
            profile = self.client.get("/api/me", headers=headers).json()
            self.assertEqual(profile["id"], name)
            self.assertNotIn("password_hash", profile)
            preview = self.client.post("/api/clearing-preview", json={}, headers=headers).json()
            self.assertEqual([row["id"] for row in preview["participants"]], [name])

    def test_forged_old_and_expired_sessions_are_rejected(self):
        headers = self.login()
        for invalid in ("Bearer gridlink-bob", headers["Authorization"] + "x", "Basic invalid"):
            bad = {"Authorization": invalid}
            for route in ("/api/me", "/api/clearing-summary"):
                self.assertEqual(self.client.get(route, headers=bad).status_code, 401)
            self.assertEqual(self.client.post("/api/clearing-preview", json={}, headers=bad).status_code, 401)
        with patch("app.main.time.time", return_value=time.time() + 86401):
            self.assertEqual(self.client.get("/api/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/api/login", json={
            "email": "alice@example.com", "password": "wrong"}).status_code, 401)

    def test_signup_issues_a_session_for_the_registered_member(self):
        with patch("app.main.register_participant", return_value=Participant(**self.rows[0])):
            response = self.client.post("/api/signup", json={
                "name": "Alice", "email": "alice@example.com", "password": "correct-password",
                "pod": "PRIVATEALICE", "type": "consumer", "load_kw": 2})
        self.assertEqual(response.status_code, 201)
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        self.assertEqual(self.client.get("/api/me", headers=headers).json()["id"], "alice")

    def test_logout_revokes_only_the_current_session(self):
        alice = self.login("alice")
        bob = self.login("bob")
        self.assertEqual(self.client.post("/api/logout", headers=alice).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=alice).status_code, 401)
        self.assertEqual(self.client.get("/api/me", headers=bob).status_code, 200)


if __name__ == "__main__":
    unittest.main()
