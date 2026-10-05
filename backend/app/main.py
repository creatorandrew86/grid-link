import hmac
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Database
from .engine import clear_market
from .models import MarketSettings, Participant, ParticipantInput
from .sign_up import SignupInput, register_participant, verify_password
from .battery import BatteryScenario, dataset_info, simulate
from .weather import live_outlook
from .community_battery import (BatteryInterest, ComparisonInput, InvitationInput, MeasurementBatch, TransferRequest,
                                compare_batteries, measured_days)


def create_app():
    database = Database()
    # ponytail: sessions live in one process; use shared storage for multiple workers.
    sessions = {}

    def issue_session(participant_id):
        now = time.time()
        for token, (_, expires) in list(sessions.items()):
            if expires <= now:
                sessions.pop(token, None)
        token = secrets.token_urlsafe(32)
        sessions[token] = (participant_id, now + 86400)
        return token

    def session_member(authorization):
        if not authorization:
            return None
        token = authorization.removeprefix("Bearer ")
        session = sessions.get(token) if authorization.startswith("Bearer ") else None
        if not session or session[1] <= time.time():
            raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")
        return session[0]

    @asynccontextmanager
    async def lifespan(app):
        database.initialize()
        yield

    app = FastAPI(title="GridLink", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization", "x-clearing-token"],
    )

    @app.exception_handler(httpx.HTTPError)
    async def database_unavailable(request, error):
        if isinstance(error, httpx.HTTPStatusError):
            try:
                code = error.response.json().get("code")
            except (ValueError, AttributeError):
                code = None
            if code in {"42P01", "42703", "PGRST204", "PGRST205"}:
                return JSONResponse(status_code=503, content={"detail":
                    "Community battery planning needs the add_community_battery_planning.sql database migration."})
        return JSONResponse(status_code=503, content={"detail": "The community database is unavailable. Try again shortly."})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "storage": database.mode, "mode": "simulation"}

    @app.get("/api/community")
    def community():
        return {"participant_count": len(database.participants())}

    @app.post("/api/signup", status_code=201)
    def signup(member: SignupInput):
        try:
            participant = register_participant(database, member)
            return {**participant.model_dump(), "access_token": issue_session(participant.id)}
        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/api/login")
    def login(payload: dict):
        email = payload.get("email") if isinstance(payload, dict) else None
        password = payload.get("password") if isinstance(payload, dict) else None
        if not isinstance(email, str) or not email.strip():
            raise HTTPException(status_code=422, detail="Email is required.")
        if not isinstance(password, str) or not password:
            raise HTTPException(status_code=422, detail="Password is required.")

        clean_email = email.strip().lower()
        participant = database.get_participant_by_email(clean_email)
        if not participant:
            raise HTTPException(status_code=404, detail="No account found with this email address.")

        stored_password = participant.get("password_hash") or participant.get("password") or ""
        if not verify_password(password, stored_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect password. The introduced password does not match.",
            )

        safe_user = {k: v for k, v in participant.items() if k not in ("password_hash", "password")}
        return {"access_token": issue_session(participant['id']), "user": safe_user}

    @app.post("/api/logout")
    def logout(authorization: str = Header(default="")):
        if authorization.startswith("Bearer "):
            sessions.pop(authorization.removeprefix("Bearer "), None)
        return {"status": "ok"}

    @app.get("/api/me")
    def me(authorization: str = Header(default="")):
        participant_id = session_member(authorization)
        if not participant_id:
            raise HTTPException(status_code=401, detail="Authentication required.")
        rows = database.remote("GET", "participants", query=f"?id=eq.{participant_id}&limit=1")
        if not rows:
            raise HTTPException(status_code=404, detail="Member account not found.")
        return {k: v for k, v in rows[0].items() if k not in ("password_hash", "password")}

    @app.get("/api/market-settings")
    def settings(authorization: str = Header(default="")):
        member = me(authorization) if session_member(authorization) else None
        return database.settings(member.get("community_id") if member else None)

    @app.put("/api/market-settings")
    def save_settings(settings: MarketSettings, authorization: str = Header(default="")):
        member = me(authorization) if session_member(authorization) else None
        database.save_settings(settings, member.get("community_id") if member else None)
        return settings

    def summary(settings=None, community_id=None):
        now = datetime.now(timezone.utc)
        slot = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        return {
            **clear_market(database.participants(community_id), settings or database.settings(community_id)),
            "interval_start": slot.isoformat().replace("+00:00", "Z"),
            "mode": "simulation",
            "storage": database.mode,
        }

    def member_summary(settings, authorization):
        participant_id = session_member(authorization)
        member = me(authorization) if participant_id else None
        result = summary(settings, member.get("community_id") if member else None)
        result["participant_count"] = len(result["participants"])
        result["participants"] = [row for row in result["participants"] if row["id"] == participant_id]
        return result

    @app.get("/api/clearing-summary")
    def clearing_summary(authorization: str = Header(default="")):
        return member_summary(None, authorization)

    @app.post("/api/clearing-preview")
    def clearing_preview(settings: MarketSettings, authorization: str = Header(default="")):
        return member_summary(settings, authorization)

    @app.get("/api/battery/dataset")
    def battery_dataset():
        return dataset_info()

    @app.post("/api/battery/simulate")
    def battery_simulate(scenario: BatteryScenario):
        try:
            return simulate(scenario)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    def community_member(authorization):
        member = me(authorization)
        if not member.get("community_id"):
            raise HTTPException(status_code=409, detail="Your account is not assigned to a community.")
        return member

    @app.get("/api/community-battery")
    def community_battery(authorization: str = Header(default="")):
        member = community_member(authorization)
        cid = member["community_id"]
        community = database.community_details(cid)
        participants = database.participants(cid)
        ids = {p.id for p in participants}
        interests = [r for r in database.battery_interests(cid) if r["participant_id"] in ids]
        _, coverage = measured_days(database.measured_history(cid), community.get("timezone") or "Europe/Bucharest")
        return {"community": {"id": cid, "name": community["name"],
                    "battery_policy": community.get("battery_policy", "undecided"),
                    "meter_boundary": community.get("battery_meter_boundary", "unverified")},
                "member_count": len(participants), "interested_count": sum(r["interested"] for r in interests),
                "answered_count": len(interests), "your_interest": next(
                    (r["interested"] for r in interests if r["participant_id"] == member["id"]), None),
                "coverage": coverage, "candidates": database.battery_candidates(community, member)}

    @app.post("/api/community-battery/compare")
    def community_battery_compare(request: ComparisonInput, authorization: str = Header(default="")):
        member = community_member(authorization)
        cid = member["community_id"]
        community = database.community_details(cid)
        try:
            result = compare_batteries(request, database.participants(cid),
                database.measured_history(cid) if request.source == "measured" else [],
                community.get("timezone") or "Europe/Bucharest", community.get("battery_meter_boundary", "unverified"), member["id"])
            return {**result, "community": {"id": cid, "name": community["name"]}, "analysis_scope": "current_community"}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/api/community-battery/invitation")
    def battery_invitation(request: InvitationInput, authorization: str = Header(default="")):
        member = community_member(authorization)
        origin = database.community_details(member["community_id"])
        target = str(request.target_community_id)
        if target not in {c["id"] for c in database.battery_candidates(origin, member)}:
            raise HTTPException(status_code=409, detail="This community is no longer eligible or accepting members.")
        destination = database.community_details(target)
        try:
            result = compare_batteries(request, database.participants(target),
                database.measured_history(target) if request.source == "measured" else [],
                destination.get("timezone") or "Europe/Bucharest",
                destination.get("battery_meter_boundary", "unverified"), member["id"],
                joining_member=Participant.model_validate(member),
                joining_events=database.measured_history(member["community_id"]) if request.source == "measured" else [],
                joining_timezone=origin.get("timezone") or "Europe/Bucharest")
            return {**result, "community": {"id": target, "name": destination["name"]},
                    "analysis_scope": "destination_with_you",
                    "notes": ["Invitation estimates include you joining the destination; this is a hypothetical combined community.",
                              *result.get("notes", [])]}
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.put("/api/community-battery/interest")
    def battery_interest(request: BatteryInterest, authorization: str = Header(default="")):
        member = community_member(authorization)
        database.save_battery_interest(member, request.interested)
        return {"interested": request.interested}

    @app.post("/api/community-battery/switch")
    def battery_switch(request: TransferRequest, authorization: str = Header(default="")):
        member = community_member(authorization)
        community = database.community_details(member["community_id"])
        target = str(request.target_community_id)
        if target not in {c["id"] for c in database.battery_candidates(community, member)}:
            raise HTTPException(status_code=409, detail="This community is no longer eligible or accepting members.")
        try:
            transfer = database.accept_battery_transfer(member["id"], target)
        except httpx.HTTPStatusError as error:
            if error.response.status_code in (400, 409):
                raise HTTPException(status_code=409, detail="Membership was not changed. Destination or POD eligibility needs review.") from error
            raise
        return {"transfer": transfer, "user": me(authorization)}

    @app.post("/api/community-battery/measurements", status_code=201)
    def battery_measurements(batch: MeasurementBatch, x_metering_token: str = Header(default="")):
        token = os.getenv("METERING_TOKEN", "")
        if not token or not hmac.compare_digest(x_metering_token, token):
            raise HTTPException(status_code=403, detail="A configured metering token is required.")
        community = database.community_details(str(batch.community_id))
        if community.get("battery_meter_boundary") != "shared_meter":
            raise HTTPException(status_code=409, detail="Verify the community's shared billing meter before ingesting readings.")
        members = {p.id for p in database.participants(str(batch.community_id))}
        if any(values is not None and {str(k) for k in values} != members
               for r in batch.readings for values in (r.member_loads_kwh, r.member_generation_kwh)):
            raise HTTPException(status_code=422, detail="Per-member readings must cover every current member of this community.")
        try:
            rows = database.save_measurements(batch)
            return {"stored_intervals": len(rows)}
        except ValueError as error:
            raise HTTPException(status_code=409, detail="One or more readings already exist; history was not overwritten.") from error

    @app.get("/api/battery/weather-outlook")
    def weather_outlook():
        try:
            return live_outlook()
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
            raise HTTPException(status_code=503, detail="Weather forecasts are unavailable. Historical simulations still work; try the outlook again later.") from error

    @app.post("/api/clearing-run")
    def clearing_run(x_clearing_token: str = Header(default="")):
        token = os.getenv("CLEARING_TOKEN", "")
        if not token or not hmac.compare_digest(x_clearing_token, token):
            raise HTTPException(status_code=403, detail="A configured clearing token is required.")
        result = summary()
        return database.save_clearing(result["interval_start"], result)

    return app


app = create_app()
