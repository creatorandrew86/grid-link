import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Database
from .engine import clear_market
from .models import MarketSettings, ParticipantInput
from .sign_up import SignupInput, register_participant, verify_password
from .battery import BatteryScenario, dataset_info, simulate
from .weather import live_outlook


def create_app():
    database = Database()

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
        return JSONResponse(status_code=503, content={"detail": "The community database is unavailable. Try again shortly."})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "storage": database.mode, "mode": "simulation"}

    @app.get("/api/community")
    def community():
        return database.participants()

    @app.post("/api/signup", status_code=201)
    def signup(member: SignupInput):
        try:
            return register_participant(database, member)
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
        return {"access_token": f"gridlink-{participant['id']}", "user": safe_user}

    @app.get("/api/me")
    def me(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required.")
        token = authorization.removeprefix("Bearer ").strip()
        if not token.startswith("gridlink-"):
            raise HTTPException(status_code=401, detail="Invalid session token.")
        participant_id = token.removeprefix("gridlink-")
        rows = database.remote("GET", "participants", query=f"?id=eq.{participant_id}&limit=1")
        if not rows:
            raise HTTPException(status_code=404, detail="Member account not found.")
        return {k: v for k, v in rows[0].items() if k not in ("password_hash", "password")}

    @app.get("/api/market-settings")
    def settings():
        return database.settings()

    @app.put("/api/market-settings")
    def save_settings(settings: MarketSettings):
        database.save_settings(settings)
        return settings

    def summary(settings=None):
        now = datetime.now(timezone.utc)
        slot = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        return {
            **clear_market(database.participants(), settings or database.settings()),
            "interval_start": slot.isoformat().replace("+00:00", "Z"),
            "mode": "simulation",
            "storage": database.mode,
        }

    @app.get("/api/clearing-summary")
    def clearing_summary():
        return summary()

    @app.post("/api/clearing-preview")
    def clearing_preview(settings: MarketSettings):
        return summary(settings)

    @app.get("/api/battery/dataset")
    def battery_dataset():
        return dataset_info()

    @app.post("/api/battery/simulate")
    def battery_simulate(scenario: BatteryScenario):
        try:
            return simulate(scenario)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

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
