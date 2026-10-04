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
from .models import MarketSettings
from .sign_up import SignupInput, register_participant, verify_password


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
        email = payload.get("email", "").strip().lower()
        password = payload.get("password", "")
        if not email:
            raise HTTPException(status_code=422, detail="Email is required.")
        if not password:
            raise HTTPException(status_code=422, detail="Password is required.")

        participant = database.get_participant_by_email(email)
        if not participant:
            raise HTTPException(status_code=404, detail="No account found with this email address.")

        stored_password = participant.get("password_hash") or participant.get("password") or ""
        if not verify_password(password, stored_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect password. The introduced password does not match.",
            )

        return {"access_token": f"gridlink-{participant['id']}", "user": participant}

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

    @app.post("/api/clearing-run")
    def clearing_run(x_clearing_token: str = Header(default="")):
        token = os.getenv("CLEARING_TOKEN", "")
        if not token or not hmac.compare_digest(x_clearing_token, token):
            raise HTTPException(status_code=403, detail="A configured clearing token is required.")
        result = summary()
        return database.save_clearing(result["interval_start"], result)

    return app


app = create_app()
