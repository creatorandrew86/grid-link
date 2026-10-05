"""Participant registration and verification for GridLink."""
import hashlib
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .database import Database
from .models import Participant


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or not isinstance(password, str) or "$" not in stored_hash:
        return False
    try:
        salt, hash_val = stored_hash.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return secrets.compare_digest(dk.hex(), hash_val)
    except Exception:
        return False


class SignupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    password: str = Field(min_length=8, max_length=128)
    pod: str = Field(pattern=r"^[A-Z0-9]{10,36}$")
    type: Literal["consumer", "prosumer"]
    load_kw: float = Field(ge=0, le=1000)
    solar_kwp: float = Field(default=0, ge=0, le=1000)


def verify_pod(db: Database, pod: str):
    clean_pod = pod.strip().upper()
    try:
        approved = db.remote("GET", "approved_pods", query=f"?pod=eq.{clean_pod}&is_active=eq.true")
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=503, detail="The community database is unavailable. Try again shortly.") from err

    if not approved:
        raise HTTPException(status_code=400, detail="POD is invalid or not approved for this grid community.")

    try:
        existing = db.remote("GET", "participants", query=f"?pod=eq.{clean_pod}&select=id&limit=1")
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=503, detail="The community database is unavailable. Try again shortly.") from err

    if existing:
        raise HTTPException(status_code=409, detail="A participant with this POD is already registered.")
    return approved[0].get("community_id")


def register_participant(db: Database, form: SignupInput) -> Participant:
    community_id = verify_pod(db, form.pod)

    row = {
        "name": form.name.strip(),
        "email": form.email.strip().lower(),
        "password_hash": hash_password(form.password),
        "pod": form.pod.strip().upper(),
        "type": form.type,
        "load_kw": form.load_kw,
        "solar_kwp": form.solar_kwp,
    }
    if community_id:
        row["community_id"] = community_id

    return db.insert_participant(row)
