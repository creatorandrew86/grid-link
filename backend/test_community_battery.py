"""Measured ROI, cost allocation, community isolation, and voluntary-switch checks."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.community_battery import (BatteryDesign, ComparisonInput, Measurement, MeasurementBatch,
                                   compare_batteries, financial_projection, measured_days, include_joining_member)
from app.models import MarketSettings, Participant
from app.sign_up import SignupInput, hash_password, register_participant
from app.database import Database

with patch("app.database.Database.__init__", return_value=None):
    from app.main import create_app

ALICE = "00000000-0000-0000-0000-000000000001"
BOB = "00000000-0000-0000-0000-000000000002"
HOME = "00000000-0000-0000-0000-000000000010"
OTHER = "00000000-0000-0000-0000-000000000020"


def design(**changes):
    return BatteryDesign(chemistry="LFP", capacity_kwh=10, power_kw=5, installed_cost_ron=3000,
                         efficiency=1, usable_fraction=.9, service_years=10, annual_fade=0,
                         annual_maintenance_ron=0, **changes)


def measured_events(days=30, member_readings=True):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for hour in range(days * 24):
        row = {"load_kwh": 1, "generation_kwh": 0,
               "import_price_ron": .1 if hour % 24 < 6 else 1, "export_price_ron": 0}
        if member_readings:
            row["member_loads_kwh"] = {ALICE: .25, BOB: .75}
        rows.append({"interval_start": (start + timedelta(hours=hour)).isoformat(), "summary": {
            "mode": "measured", "currency": "RON", "meter_boundary": "shared_meter",
            "battery_free_baseline": True, "interval_minutes": 60, "measurement": row}})
    return rows


def participants():
    return [Participant(id=ALICE, community_id=HOME, name="Alice", type="consumer", load_kw=.25),
            Participant(id=BOB, community_id=HOME, name="Bob", type="consumer", load_kw=.75)]


class CommunityBatteryChecks(unittest.TestCase):
    def test_hand_calculated_cash_projection_and_service_life(self):
        d = design().model_copy(update={"service_years": 3})
        request = ComparisonInput(designs=[d], discount_rate=0)
        result = financial_projection(1000, d, request)
        self.assertEqual(result["years"], 3)
        self.assertEqual(result["payback_years"], 3)
        self.assertEqual(result["roi_pct"], 0)
        self.assertEqual(result["npv_ron"], 0)
        self.assertEqual(result["timeline"][-1]["cumulative_ron"], 0)
        self.assertIsNone(financial_projection(0, d, request)["payback_years"])
        discounted = financial_projection(1000, d, request.model_copy(update={"discount_rate": .1}))
        self.assertAlmostEqual(discounted["npv_ron"], 1000 / 1.1 + 1000 / 1.1**2 + 1000 / 1.1**3 - 3000)

    def test_real_optimiser_cash_savings_and_both_funding_allocations(self):
        request = ComparisonInput(designs=[design()], dispatch_wear_ron_per_kwh=0)
        result = compare_batteries(request, participants(), measured_events(), "UTC", "shared_meter", ALICE)
        self.assertEqual(result["status"], "ready")
        row = result["designs"][0]
        self.assertAlmostEqual(row["sample_cash_saving_ron"], 30 * 9 * .9, places=5)
        self.assertAlmostEqual(row["annual_cash_saving_ron"], 365 * 9 * .9, places=5)
        self.assertEqual(row["member_allocations"]["equal_share"]["contribution_ron"], 1500)
        self.assertEqual(row["member_allocations"]["consumption_share"]["contribution_ron"], 750)
        self.assertAlmostEqual(row["member_allocations"]["consumption_share"]["first_year_saving_ron"],
                               row["projections"]["base"]["first_year_net_saving_ron"] * .25)
        self.assertNotIn("member_loads_kwh", str(result))

    def test_missing_measurements_and_short_samples_never_manufacture_roi(self):
        request = ComparisonInput(designs=[design()])
        result = compare_batteries(request, participants(), [], "UTC", "shared_meter", ALICE)
        self.assertEqual(result["status"], "no_measured_history")
        self.assertEqual(result["designs"], [])
        short = compare_batteries(request, participants(), measured_events(1, False), "UTC", "shared_meter", ALICE)
        self.assertEqual(short["status"], "limited_history")
        self.assertIsNone(short["designs"][0]["projections"])
        self.assertIsNone(short["designs"][0]["annual_cash_saving_ron"])
        self.assertIsNone(short["designs"][0]["member_allocations"]["consumption_share"]["share"])
        unverified = compare_batteries(request, participants(), measured_events(1), "UTC", "separate_meters", ALICE)
        self.assertEqual(unverified["status"], "meter_boundary_unconfirmed")
        with self.assertRaises(ValueError):
            compare_batteries(request.model_copy(update={"source": "planning"}), participants(), [], "UTC", "unverified", ALICE)

    def test_simulated_wrong_currency_incomplete_and_duplicate_days_are_excluded(self):
        events = measured_events(1)
        days, coverage = measured_days(events, "UTC")
        self.assertEqual(len(days), 1)
        for summary in ({"mode": "simulation"}, {"currency": "EUR"}, {"battery_free_baseline": False}):
            bad = [{**r, "summary": {**r["summary"], **summary}} for r in events]
            days, coverage = measured_days(bad, "UTC")
            self.assertEqual(days, [])
            self.assertEqual(coverage["excluded_intervals"], 24)
        for bad in (events[:-1], events + [events[0]]):
            self.assertEqual(measured_days(bad, "UTC")[1]["incomplete_days"], 1)

    def test_demo_archives_are_explicit_and_never_count_as_measured_history(self):
        demo = [{**r, "summary": {**r["summary"], "mode": "demo_battery"}} for r in measured_events(30)]
        self.assertEqual(measured_days(demo, "UTC")[0], [])
        self.assertEqual(len(measured_days(demo, "UTC", demo_mode=True)[0]), 30)
        result = compare_batteries(ComparisonInput(designs=[design()]), participants(), demo,
                                  "UTC", "shared_meter", ALICE, demo_mode=True)
        self.assertEqual(result["source"], "demo_replay")
        self.assertIsInstance(result["purchase_recommended"], bool)
        json_safe = __import__("json").dumps(result)
        self.assertIn('"source": "demo_replay"', json_safe)

    def test_demo_database_uses_only_demo_metadata_and_rebuilds_hypothetical_roster(self):
        with patch.object(Database, "__init__", return_value=None):
            db = Database()
        db.remote = MagicMock(return_value=[{"id": HOME, "description": __import__("json").dumps({
            "gridlink_demo": True, "battery_analysis_config": {"data_mode": "demo_replay"}})}])
        self.assertTrue(db.community_details(HOME)["is_demo"])
        db.remote.return_value = [{"id": HOME, "description": "Real community"}]
        self.assertNotIn("is_demo", db.community_details(HOME))
        profile = {ALICE: {"load_kwh": .25, "generation_kwh": 0}, BOB: {"load_kwh": .75, "generation_kwh": .5}}
        event = {"interval_start": "2025-01-01T00:00:00Z", "summary": {
            "mode": "demo_battery", "demo_member_profiles": profile, "measurement": {}}}
        db.remote.return_value = [event]
        db.participants = MagicMock(return_value=[participants()[1]])
        self.assertEqual(db.demo_history(HOME)[0]["summary"]["measurement"]["load_kwh"], .75)
        db.participants.return_value = participants()
        self.assertEqual(db.demo_history(HOME)[0]["summary"]["measurement"]["load_kwh"], 1)
        self.assertIn("summary->>mode=eq.demo_battery", db.remote.call_args.kwargs["query"])

    def test_dst_day_is_complete_without_inventing_a_missing_hour(self):
        zone = ZoneInfo("Europe/Bucharest")
        start = datetime(2025, 3, 30, tzinfo=zone).astimezone(timezone.utc)
        template = measured_events(1)[0]["summary"]
        events = [{"interval_start": (start + timedelta(hours=i)).isoformat(), "summary": template} for i in range(23)]
        days, _ = measured_days(events, "Europe/Bucharest")
        self.assertEqual(len(days), 1)
        self.assertEqual(len(days[0]), 23)

    def test_measurements_validate_ownership_totals_time_and_duplicates(self):
        payload = {"interval_start": "2025-01-01T00:00:00Z", "load_kwh": 1, "generation_kwh": 0,
                   "import_price_ron": 1, "export_price_ron": 0}
        for bad in ({"member_loads_kwh": {ALICE: 2}}, {"member_loads_kwh": {ALICE: float("nan")}},
                    {"interval_start": "2025-01-01T00:01:00Z"}, {"interval_start": "2025-01-01T00:00:00"},
                    {"interval_start": "2099-01-01T00:00:00Z"}):
            with self.assertRaises(ValidationError):
                Measurement(**{**payload, **bad})
        with self.assertRaises(ValidationError):
            MeasurementBatch(community_id=HOME, shared_meter_confirmed=True,
                             battery_free_baseline_confirmed=True, readings=[payload, payload])

    def test_quarter_hour_meter_data_and_all_twenty_seven_technology_size_options(self):
        designs = [design().model_copy(update={"chemistry": chemistry, "capacity_kwh": capacity,
                   "power_kw": capacity / 2, "efficiency": efficiency, "usable_fraction": usable})
                   for chemistry, efficiency, usable in (("LFP", .92, .9), ("NMC", .9, .85), ("Lead-acid", .8, .5))
                   for capacity in (5, 10, 15, 20, 30, 40, 60, 80, 100)]
        events = []
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(96):
            events.append({"interval_start": (start + timedelta(minutes=15*i)).isoformat(), "summary": {
                "mode": "measured", "currency": "RON", "meter_boundary": "shared_meter",
                "battery_free_baseline": True, "interval_minutes": 15, "measurement": {
                    "load_kwh": .25, "generation_kwh": 0, "import_price_ron": .1 if i < 24 else 1,
                    "export_price_ron": 0, "member_loads_kwh": {ALICE: .0625, BOB: .1875}}}})
        result = compare_batteries(ComparisonInput(designs=designs), participants(), events, "UTC", "shared_meter", ALICE)
        self.assertEqual(len(result["designs"]), 27)
        self.assertEqual(result["coverage"]["valid_intervals"], 96)
        for row in result["designs"]:
            self.assertNotIn("error", row)
            self.assertGreater(row["sample_cash_saving_ron"], 0)
            self.assertGreaterEqual(row["sample_saving_after_wear_ron"], -1e-5)

    def test_best_size_uses_npv_and_negative_options_do_not_recommend_purchase(self):
        designs = [design().model_copy(update={"capacity_kwh": capacity, "power_kw": capacity / 2,
                   "installed_cost_ron": cost}) for capacity, cost in ((5, 1000), (10, 3000), (40, 40000))]
        request = ComparisonInput(designs=designs, dispatch_wear_ron_per_kwh=0)
        result = compare_batteries(request, participants(), measured_events(), "UTC", "shared_meter", ALICE)
        self.assertEqual(result["best_design_index"], 1)
        self.assertTrue(result["purchase_recommended"])
        expensive = request.model_copy(update={"designs": [design().model_copy(update={"installed_cost_ron": 1000000})]})
        result = compare_batteries(expensive, participants(), measured_events(), "UTC", "shared_meter", ALICE)
        self.assertEqual(result["best_design_index"], 0)
        self.assertFalse(result["purchase_recommended"])

    def test_invitation_combines_your_readings_with_destination_tariffs_and_population(self):
        origin = measured_events()
        target = measured_events()
        for event in target:
            event["summary"]["measurement"]["member_loads_kwh"] = {BOB: 1}
            event["summary"]["measurement"]["import_price_ron"] *= 2
        request = ComparisonInput(designs=[design()], dispatch_wear_ron_per_kwh=0)
        current = compare_batteries(request, participants(), origin, "UTC", "shared_meter", ALICE)
        result = compare_batteries(request, [participants()[1]], target, "UTC", "shared_meter", ALICE,
                                  joining_member=participants()[0], joining_events=origin)
        row = result["designs"][0]
        self.assertTrue(result["includes_joining_member"])
        self.assertEqual(result["member_count"], 2)
        self.assertAlmostEqual(row["sample_baseline_bill_ron"], 30 * 1.25 * (6 * .2 + 18 * 2))
        self.assertAlmostEqual(row["annual_cash_saving_ron"], 2 * current["designs"][0]["annual_cash_saving_ron"])
        self.assertEqual(row["member_allocations"]["equal_share"]["contribution_ron"], 1500)
        self.assertEqual(row["member_allocations"]["consumption_share"]["contribution_ron"], 600)
        self.assertEqual(target[0]["summary"]["measurement"]["load_kwh"], 1)
        self.assertNotIn("member_loads_kwh", str(result))

    def test_prosumer_invitation_requires_measured_solar_and_excludes_unmatched_days(self):
        incoming = participants()[0].model_copy(update={"type": "prosumer", "solar_kwp": 5})
        target_days, _ = measured_days(measured_events(1), "UTC")
        source = measured_events(1)
        self.assertEqual(include_joining_member(target_days, source, "UTC", incoming), [])
        for event in source:
            m = event["summary"]["measurement"]
            m["generation_kwh"] = .5
            m["member_generation_kwh"] = {ALICE: .5, BOB: 0}
        combined = include_joining_member(target_days, source, "UTC", incoming)
        self.assertEqual(combined[0][0]["load_kwh"], 1.25)
        self.assertEqual(combined[0][0]["pv_kwh"], .5)
        shifted = [{**event, "interval_start": (datetime.fromisoformat(event["interval_start"]) + timedelta(days=1)).isoformat()} for event in source]
        self.assertEqual(include_joining_member(target_days, shifted, "UTC", incoming), [])
        result = compare_batteries(ComparisonInput(designs=[design()]), [participants()[1]], measured_events(1),
                                  "UTC", "shared_meter", ALICE, joining_member=incoming, joining_events=measured_events(1))
        self.assertEqual(result["status"], "joining_history_unavailable")
        self.assertEqual(result["designs"], [])

    def test_signup_and_insert_keep_the_pods_approved_community(self):
        db = MagicMock()
        db.remote.side_effect = [[{"community_id": OTHER}], []]
        form = SignupInput(name="New Member", email="new@example.com", password="correct-password",
                           pod="NEWPOD123456", type="consumer", load_kw=1)
        register_participant(db, form)
        self.assertEqual(db.insert_participant.call_args.args[0]["community_id"], OTHER)
        with patch.object(Database, "__init__", return_value=None):
            real = Database()
        real._community_id = HOME
        real.remote = MagicMock(side_effect=lambda method, table, payload: [payload])
        member = real.insert_participant({"id": ALICE, "community_id": OTHER, "name": "Alice",
                                          "type": "consumer", "load_kw": 1})
        self.assertEqual(member.community_id, OTHER)

    def test_suggestions_require_explicit_pod_approval_in_addition_to_network_zone(self):
        with patch.object(Database, "__init__", return_value=None):
            db = Database()
        db.remote = MagicMock(side_effect=[[{"battery_eligible_communities": [OTHER]}],
                                            [{"id": OTHER, "name": "Allowed"}, {"id": HOME, "name": "Not allowed"}]])
        result = db.battery_candidates({"id": HOME, "network_zone": "zone-a"}, {"id": ALICE, "pod": "ALICEPOD1234"})
        self.assertEqual([r["id"] for r in result], [OTHER])
        db.remote = MagicMock(return_value=[{"battery_eligible_communities": []}])
        self.assertEqual(db.battery_candidates({"id": HOME, "network_zone": "zone-a"}, {"pod": "ALICEPOD1234"}), [])
        self.assertEqual(db.remote.call_count, 1)


class CommunityBatteryApiChecks(unittest.TestCase):
    def setUp(self):
        self.member = {**participants()[0].model_dump(), "email": "alice@example.com", "pod": "ALICEPOD1234",
                       "password_hash": hash_password("correct-password")}
        with patch("app.main.Database", autospec=True) as factory:
            self.db = factory.return_value
            self.db.mode = "test"
            self.db.get_participant_by_email.return_value = self.member
            self.db.remote.side_effect = lambda *a, **kw: [self.member]
            self.db.community_details.return_value = {"id": HOME, "name": "Home Community", "timezone": "UTC",
                "network_zone": "zone-a", "battery_meter_boundary": "shared_meter", "battery_policy": "declined"}
            self.db.participants.return_value = participants()
            self.db.settings.return_value = MarketSettings()
            self.db.measured_history.return_value = measured_events(1)
            self.db.battery_interests.return_value = [{"participant_id": ALICE, "interested": True},
                {"participant_id": BOB, "interested": False}, {"participant_id": "outsider", "interested": True}]
            self.db.battery_candidates.return_value = [{"id": OTHER, "name": "Battery Community", "battery_policy": "approved"}]
            self.client = TestClient(create_app())
        login = self.client.post("/api/login", json={"email": "alice@example.com", "password": "correct-password"})
        self.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_member_context_aggregate_privacy_and_community_scoping(self):
        self.assertEqual(self.client.get("/api/community-battery").status_code, 401)
        response = self.client.get("/api/community-battery", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["interested_count"], 1)
        self.assertEqual(response.json()["answered_count"], 2)
        self.assertNotIn(BOB, response.text)
        self.assertNotIn("password_hash", response.text)
        self.db.participants.assert_called_with(HOME)
        self.db.measured_history.assert_called_with(HOME)
        self.client.get("/api/community", headers=self.headers)
        self.db.participants.assert_called_with(HOME)
        self.client.get("/api/clearing-summary", headers=self.headers)
        self.db.settings.assert_called_with(HOME)
        self.db.participants.assert_called_with(HOME)
        self.assertEqual(self.client.put("/api/market-settings", json={}, headers=self.headers).status_code, 403)
        self.db.save_settings.assert_not_called()
        with patch.dict("os.environ", {"CLEARING_TOKEN": "operator-secret"}):
            response = self.client.put("/api/market-settings", json={},
                headers={**self.headers, "x-clearing-token": "operator-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.save_settings.call_args.args[1], HOME)

    def test_automatic_analysis_requires_sourced_config_and_rejects_member_overrides(self):
        self.assertEqual(self.client.post("/api/community-battery/analysis", json={}).status_code, 401)
        response = self.client.post("/api/community-battery/analysis", headers=self.headers, json={})
        self.assertEqual(response.json()["status"], "analysis_configuration_missing")
        self.assertEqual(response.json()["designs"], [])
        self.assertEqual(self.client.post("/api/community-battery/analysis", headers=self.headers,
            json={"designs": [design().model_dump()], "source": "planning"}).status_code, 422)

    def test_automatic_analysis_uses_each_communitys_stored_catalogue(self):
        def configured(cid):
            battery = design().model_dump()
            battery.update(capacity_kwh=5 if cid == HOME else 20, installed_cost_ron=5000 if cid == HOME else 15000)
            return {"id": cid, "name": "Origin" if cid == HOME else "Destination", "timezone": "UTC",
                    "battery_meter_boundary": "shared_meter", "battery_analysis_config": {
                        "comparison": ComparisonInput(designs=[battery]).model_dump(),
                        "quote_source": "Test supplier quote", "quote_date": "2025-01-01",
                        "assumptions_source": "Test connection contract and approved financial policy"}}
        self.db.community_details.side_effect = configured
        response = self.client.post("/api/community-battery/analysis", headers=self.headers, json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["designs"][0]["design"]["capacity_kwh"], 5)
        self.assertEqual(response.json()["input_sources"]["battery"], "Test supplier quote")
        self.db.participants.side_effect = lambda cid: participants() if cid == HOME else [participants()[1]]
        events = measured_events(1)
        target_events = [{**r, "summary": {**r["summary"], "measurement": {
            **r["summary"]["measurement"], "member_loads_kwh": {BOB: r["summary"]["measurement"]["load_kwh"]}}}}
            for r in events]
        self.db.measured_history.side_effect = lambda cid: events if cid == HOME else target_events
        response = self.client.post("/api/community-battery/analysis", headers=self.headers,
                                    json={"target_community_id": OTHER})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["community"]["name"], "Destination")
        self.assertEqual(response.json()["designs"][0]["design"]["capacity_kwh"], 20)
        self.assertEqual(response.json()["member_count"], 2)
        self.db.accept_battery_transfer.assert_not_called()
        self.db.battery_candidates.return_value = []
        self.assertEqual(self.client.post("/api/community-battery/analysis", headers=self.headers,
            json={"target_community_id": OTHER}).status_code, 409)

    def test_automatic_analysis_does_not_use_incomplete_or_planning_configuration(self):
        community = self.db.community_details.return_value
        config = {"comparison": ComparisonInput(designs=[design()]).model_dump(),
                  "quote_source": "Test quote", "quote_date": "2025-01-01", "assumptions_source": "Test policy"}
        community["battery_analysis_config"] = config
        config["comparison"]["source"] = "planning"
        response = self.client.post("/api/community-battery/analysis", headers=self.headers, json={})
        self.assertEqual(response.json()["status"], "analysis_configuration_missing")
        config["comparison"]["source"] = "measured"
        del config["comparison"]["connection_import_kw"]
        response = self.client.post("/api/community-battery/analysis", headers=self.headers, json={})
        self.assertEqual(response.json()["designs"], [])

    def test_preferences_and_roi_cannot_target_someone_elses_community(self):
        response = self.client.put("/api/community-battery/interest", headers=self.headers, json={"interested": False})
        self.assertEqual(response.status_code, 200)
        member, interested = self.db.save_battery_interest.call_args.args
        self.assertEqual(member["id"], ALICE)
        self.assertFalse(interested)
        payload = {"designs": [design().model_dump()], "community_id": OTHER}
        self.assertEqual(self.client.post("/api/community-battery/compare", headers=self.headers, json=payload).status_code, 422)
        payload.pop("community_id")
        response = self.client.post("/api/community-battery/compare", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(BOB, response.text)

    def test_only_explicit_acceptance_switches_the_signed_in_member(self):
        self.client.get("/api/community-battery", headers=self.headers)
        self.db.accept_battery_transfer.assert_not_called()
        self.db.accept_battery_transfer.return_value = {"status": "accepted", "community_id": OTHER}
        def accept(*args):
            self.member["community_id"] = OTHER
            return {"status": "accepted", "community_id": OTHER}
        self.db.accept_battery_transfer.side_effect = accept
        response = self.client.post("/api/community-battery/switch", headers=self.headers,
                                    json={"target_community_id": OTHER})
        self.assertEqual(response.status_code, 200, response.text)
        self.db.accept_battery_transfer.assert_called_once_with(ALICE, OTHER)
        self.assertEqual(response.json()["user"]["community_id"], OTHER)
        self.assertNotIn("password_hash", response.text)
        self.assertEqual(self.client.post("/api/community-battery/switch", json={"target_community_id": OTHER}).status_code, 401)

    def test_invitation_is_destination_scoped_read_only_and_checks_eligibility(self):
        def community(cid):
            return {"id": cid, "name": "Destination" if cid == OTHER else "Origin",
                    "timezone": "UTC", "battery_meter_boundary": "shared_meter"}
        self.db.community_details.side_effect = community
        self.db.participants.side_effect = lambda cid: [participants()[1]] if cid == OTHER else participants()
        destination = measured_events(1)
        for event in destination:
            event["summary"]["measurement"]["member_loads_kwh"] = {BOB: 1}
        self.db.measured_history.side_effect = lambda cid: destination if cid == OTHER else measured_events(1)
        payload = {"target_community_id": OTHER, "designs": [design().model_dump()]}
        self.assertEqual(self.client.post("/api/community-battery/invitation", json=payload).status_code, 401)
        response = self.client.post("/api/community-battery/invitation", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["community"], {"id": OTHER, "name": "Destination"})
        self.assertEqual(response.json()["analysis_scope"], "destination_with_you")
        self.assertEqual(response.json()["member_count"], 2)
        self.assertNotIn(BOB, response.text)
        self.assertNotIn("password_hash", response.text)
        self.db.accept_battery_transfer.assert_not_called()
        self.assertEqual(self.member["community_id"], HOME)
        self.db.battery_candidates.return_value = []
        self.assertEqual(self.client.post("/api/community-battery/invitation", headers=self.headers, json=payload).status_code, 409)

    def test_planning_invitation_includes_you_without_reading_measured_history(self):
        self.db.participants.return_value = [participants()[1]]
        self.db.community_details.return_value = {"id": OTHER, "name": "Destination", "timezone": "UTC"}
        days, _ = measured_days(measured_events(1), "UTC")
        with patch("app.community_battery.planning_days", return_value=days) as planner:
            response = self.client.post("/api/community-battery/invitation", headers=self.headers, json={
                "target_community_id": OTHER, "designs": [design().model_dump()],
                "source": "planning", "shared_meter_confirmed": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual({p.id for p in planner.call_args.args[0]}, {ALICE, BOB})
        self.db.measured_history.assert_not_called()
        self.assertEqual(response.json()["source"], "planning")

    def test_ineligible_or_changed_destinations_do_not_switch_members(self):
        self.db.battery_candidates.return_value = []
        self.assertEqual(self.client.post("/api/community-battery/switch", headers=self.headers,
            json={"target_community_id": OTHER}).status_code, 409)
        self.db.accept_battery_transfer.assert_not_called()
        self.db.battery_candidates.return_value = [{"id": OTHER}]
        response = httpx.Response(400, request=httpx.Request("POST", "https://example.com/rpc"))
        self.db.accept_battery_transfer.side_effect = httpx.HTTPStatusError("Eligibility changed", request=response.request, response=response)
        self.assertEqual(self.client.post("/api/community-battery/switch", headers=self.headers,
            json={"target_community_id": OTHER}).status_code, 409)
        self.assertEqual(self.member["community_id"], HOME)

    def test_metering_requires_server_secret_and_complete_member_coverage(self):
        reading = {"interval_start": "2025-01-01T00:00:00Z", "interval_minutes": 60, "load_kwh": 1,
                   "generation_kwh": 0, "import_price_ron": 1, "export_price_ron": 0}
        payload = {"community_id": HOME, "shared_meter_confirmed": True,
                   "battery_free_baseline_confirmed": True, "readings": [reading]}
        self.assertEqual(self.client.post("/api/community-battery/measurements", json=payload, headers=self.headers).status_code, 403)
        with patch.dict("os.environ", {"METERING_TOKEN": "test-meter-secret"}):
            headers = {"x-metering-token": "test-meter-secret"}
            self.db.save_measurements.return_value = [reading]
            self.assertEqual(self.client.post("/api/community-battery/measurements", json=payload, headers=headers).status_code, 201)
            payload["readings"][0]["member_loads_kwh"] = {ALICE: 1}
            self.assertEqual(self.client.post("/api/community-battery/measurements", json=payload, headers=headers).status_code, 422)


if __name__ == "__main__":
    unittest.main()
