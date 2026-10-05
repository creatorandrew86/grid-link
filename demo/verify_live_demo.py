"""Exercise login, funding, invitations, switch and persistence on the running local app."""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_demo import EMAIL, PASSWORD, uid


def verify():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=120) as client:
        login = client.post("/api/login", json={"email": EMAIL, "password": PASSWORD})
        login.raise_for_status()
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        assert login.json()["user"]["community_id"] == uid("origin"), "Reset demo before verification."
        context = client.get("/api/community-battery"); context.raise_for_status()
        assert context.json()["community"]["is_demo"] is True
        assert context.json()["coverage"]["complete_days"] == 30
        initial = client.post("/api/community-battery/analysis", json={}); initial.raise_for_status()
        assert initial.json()["source"] == "demo_replay"
        assert len(initial.json()["designs"]) == 9
        assert "password_hash" not in initial.text
        interested = client.put("/api/community-battery/interest", json={"interested": True}); interested.raise_for_status()
        context = client.get("/api/community-battery").json()
        assert context["your_interest"] is True
        assert {c["id"] for c in context["candidates"]} == {uid("solar"), uid("flat")}
        solar = client.post("/api/community-battery/analysis", json={"target_community_id": uid("solar")}); solar.raise_for_status()
        assert solar.json()["member_count"] == 3
        assert solar.json()["purchase_recommended"] is True
        flat = client.post("/api/community-battery/analysis", json={"target_community_id": uid("flat")}); flat.raise_for_status()
        assert flat.json()["purchase_recommended"] is False
        assert client.get("/api/me").json()["community_id"] == uid("origin"), "Viewing invitations must not change membership."
        transfer = client.post("/api/community-battery/switch", json={"target_community_id": uid("solar")}); transfer.raise_for_status()
        assert transfer.json()["transfer"]["status"] == "accepted"
        assert client.get("/api/me").json()["community_id"] == uid("solar")
        joined = client.post("/api/community-battery/analysis", json={}); joined.raise_for_status()
        assert joined.json()["member_count"] == 3
        assert joined.json()["coverage"]["replayed_days"] == 30
        best = joined.json()["best_design_index"]
        assert joined.json()["designs"][best]["member_allocations"]["consumption_share"]["share"] is not None
        assert abs(joined.json()["designs"][best]["projections"]["base"]["npv_ron"] - solar.json()["designs"][best]["projections"]["base"]["npv_ron"]) < .01
        # New session confirms the database change survives sign-out/sign-in.
        client.post("/api/logout")
        relogin = client.post("/api/login", json={"email": EMAIL, "password": PASSWORD}); relogin.raise_for_status()
        assert relogin.json()["user"]["community_id"] == uid("solar")
    result = {"status": "passed", "checks": ["login", "30-day labelled replay", "nine sizes", "saved interest",
        "eligible invitations", "destination ROI includes joiner", "uneconomic purchase rejected", "preview does not move membership",
        "atomic Supabase switch", "post-switch funding", "same ROI before/after acceptance", "membership persists after login"],
        "transfer_id": transfer.json()["transfer"]["id"]}
    (Path(__file__).parent / "live-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    verify()
