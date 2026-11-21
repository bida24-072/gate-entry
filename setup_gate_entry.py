"""One-shot project builder for the Campus Gate Entry System.

Usage (inside an empty project folder):
    python setup_gate_entry.py
Creates every file, and a .env with freshly generated random secrets.
"""
import re
import secrets
from pathlib import Path

FILES = {}
FILES['.devcontainer/devcontainer.json'] = r'''{
  "name": "gate-entry",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/node:1": { "version": "20" }
  },
  "forwardPorts": [8000],
  "postCreateCommand": "cp -n .env.example .env && pip install -r backend/requirements.txt",
  "customizations": {
    "vscode": {
      "extensions": ["ms-python.python", "ms-azuretools.vscode-docker"]
    }
  }
}
'''
FILES['.env.example'] = r'''# Copy to .env and change every secret before real use.
POSTGRES_USER=gate
POSTGRES_PASSWORD=change-me
POSTGRES_DB=gate
DATABASE_URL=postgresql+psycopg://gate:change-me@db:5432/gate
REDIS_URL=redis://redis:6379/0

# Shared secret with the university registration system (signs enrollment pushes)
ENROLLMENT_SHARED_SECRET=change-me-long-random
# Secret pepper used to hash card UIDs, plates, visitor tokens, gate keys
CREDENTIAL_PEPPER=change-me-long-random
# JWT signing key for dashboard users (used from step 3)
JWT_SECRET=change-me-long-random
ENROLLMENT_MAX_SKEW_SECONDS=300
'''
FILES['.github/workflows/ci.yml'] = r'''name: CI
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - run: pip install -r requirements.txt
      - run: pytest -q
'''
FILES['.gitignore'] = r'''__pycache__/
*.pyc
.env
.venv/
node_modules/
dist/
.pytest_cache/
*.sqlite
'''
FILES['CLAUDE.md'] = r'''# Campus Gate Entry System

Real production system (not a demo) for a university: 2 student entry gates, 1 student exit,
1 vehicle entry, 1 vehicle exit, 2 guard rooms. Backend: FastAPI + SQLAlchemy 2 + Alembic +
PostgreSQL + Redis. Dashboard (later): React + Vite + TypeScript + Tailwind. Edge service
(later): Python + SQLite at each gate.

## Rules
- Allow/deny logic lives ONLY in `backend/app/decision.py` (pure functions, no I/O). Every rule needs a unit test.
- `access_events` and `audit_log` are append-only (DB triggers). Never write code that updates or deletes them.
- Never store raw photos, raw fingerprints, or plain card UIDs. Store keyed hashes (`security.hash_secret`).
- Roles: admin, registrar, guard. Guards cannot edit student records. Overrides need a reason + guard name in audit_log.
- Gates authenticate with `X-Gate-Key`; a Redis outage must never block a gate decision.
- Schema changes: `alembic revision --autogenerate`. Use fake data only; never real student data.

## Commands
- Run: `docker compose up --build`
- Seed gates: `docker compose exec api python -m app.seed`
- Create admin: `docker compose exec api python -m app.seed_admin`
- Tests: `cd backend && pytest -q`
'''
FILES['README.md'] = r'''# Campus Gate Entry System

Access control for a university campus: 2 student entry gates, 1 student exit gate,
1 vehicle entry gate, 1 vehicle exit gate, 2 guard rooms. See the system design document
for the full specification.

## Run locally

```bash
cp .env.example .env          # then change every secret
docker compose up --build     # postgres + redis + api (migrations run on start)
docker compose exec api python -m app.seed   # creates the 5 gates, prints their API keys ONCE
```

API docs: http://localhost:8000/docs  ·  health: http://localhost:8000/health

## Tests

```bash
cd backend && pip install -r requirements.txt && pytest -q
```

## Layout

```
backend/app/decision.py      pure allow/deny rules (critical path, fully unit tested)
backend/app/security.py      keyed hashing, plate normalisation, enrollment signatures
backend/app/models.py        PostgreSQL schema (students, credentials, vehicles, visitors, gates, events, audit)
backend/app/routers/         enrollment (signed push) and access (gate check) endpoints
backend/alembic/             migrations; audit tables are append-only via DB triggers
```

## Try it

Student entry (second factor is matched on the gate device and reported):

```bash
curl -X POST localhost:8000/api/v1/access/check \
  -H "X-Gate-Key: <key from seed>" -H "Content-Type: application/json" \
  -d '{"card_uid":"04A1B2C3","second_factor_type":"fingerprint","second_factor_matched":true}'
```

## Security notes

- Never commit `.env`. Rotate all secrets before any real deployment.
- In production, use a DB role for the API that has no UPDATE/DELETE on `access_events` and `audit_log`
  (the triggers are a second layer, not the only one).
- Biometrics: templates only, encrypted, with recorded consent (Botswana Data Protection Act).

## Roadmap

1. ✅ Compose stack, schema, append-only audit, decision logic, gate auth
2. ✅ Signed enrollment push, access check API
3. ⏭ Credential registration endpoints, visitor passes, revocation sync, JWT login + roles
4. ⏭ React guard dashboard (WebSocket live feed from the `gate_events` Redis channel)
5. ⏭ Gate edge service (SQLite cache, offline mode, event queue) then hardware adapters
6. ⏭ Campus server deployment, TLS, backups with restore drills
'''
FILES['backend/Dockerfile'] = r'''FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
'''
FILES['backend/alembic.ini'] = r'''[alembic]
script_location = alembic
'''
FILES['backend/alembic/env.py'] = r'''from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.models import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
'''
FILES['backend/alembic/script.py.mako'] = r'''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
FILES['backend/alembic/versions/0001_initial.py'] = r'''"""initial schema + append-only triggers

Bootstrap migration: creates all tables from the models and makes the audit
tables append-only at the database level. Later schema changes should use
`alembic revision --autogenerate`.
"""
from alembic import op

from app.models import Base

revision = "0001"
down_revision = None

APPEND_ONLY = ["access_events", "audit_log"]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())
    op.execute(
        """
        CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_mutation();"
        )


def downgrade() -> None:
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
    op.execute("DROP FUNCTION IF EXISTS forbid_mutation();")
    Base.metadata.drop_all(bind=op.get_bind())
'''
FILES['backend/app/__init__.py'] = r''''''
FILES['backend/app/audit.py'] = r'''from sqlalchemy.orm import Session

from .models import AuditLog, User


def audit(db: Session, user: User | None, action: str, detail: dict) -> None:
    """Queue an audit row in the caller's transaction (caller commits)."""
    db.add(AuditLog(actor_user_id=user.id if user else None, action=action, detail=detail))
'''
FILES['backend/app/auth.py'] = r'''from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

ph = PasswordHasher()
bearer = HTTPBearer()
TOKEN_MINUTES = 30
DUMMY_HASH = ph.hash("not-a-real-password")  # equalises login timing for unknown emails


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: int, role: str, secret: str, minutes: int = TOKEN_MINUTES) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    claims = decode_token(creds.credentials, settings.jwt_secret)
    if claims is None:
        raise HTTPException(401, "invalid or expired token")
    user = db.get(User, int(claims["sub"]))
    if user is None or not user.active:  # re-check DB so deactivation takes effect immediately
        raise HTTPException(401, "user not found or disabled")
    return user


def require_role(*roles: str):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "insufficient role")
        return user

    return dependency
'''
FILES['backend/app/config.py'] = r'''from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gate:gate@localhost:5432/gate"
    redis_url: str = "redis://localhost:6379/0"
    enrollment_shared_secret: str = "dev-only-change-me"
    credential_pepper: str = "dev-only-change-me"
    jwt_secret: str = "dev-only-change-me"
    enrollment_max_skew_seconds: int = 300


settings = Settings()
'''
FILES['backend/app/db.py'] = r'''import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return _redis
'''
FILES['backend/app/decision.py'] = r'''"""The critical path: pure allow/deny rules with no I/O.

Everything the rules need is passed in as plain values, so the logic is fully
unit-testable and can later be reused by the gate edge service offline.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Result(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REFER = "refer_to_guard"


class Reason(str, Enum):
    OK = "ok"
    UNKNOWN_CREDENTIAL = "unknown_credential"
    CREDENTIAL_REVOKED = "credential_revoked"
    STUDENT_NOT_ACTIVE = "student_not_active"
    SECOND_FACTOR_FAILED = "second_factor_failed"
    ALREADY_INSIDE = "already_inside"
    VEHICLE_UNREGISTERED = "vehicle_unregistered"
    VEHICLE_INACTIVE = "vehicle_inactive"
    VISITOR_UNKNOWN = "visitor_unknown"
    VISITOR_NOT_YET_VALID = "visitor_not_yet_valid"
    VISITOR_EXPIRED = "visitor_expired"


@dataclass(frozen=True)
class Decision:
    result: Result
    reason: Reason


def student_entry(
    *,
    credential_found: bool,
    credential_revoked: bool,
    student_status: str | None,
    student_inside: bool,
    second_factor_ok: bool,
) -> Decision:
    if not credential_found:
        return Decision(Result.DENY, Reason.UNKNOWN_CREDENTIAL)
    if credential_revoked:
        return Decision(Result.DENY, Reason.CREDENTIAL_REVOKED)
    if student_status != "active":
        return Decision(Result.DENY, Reason.STUDENT_NOT_ACTIVE)
    if not second_factor_ok:
        return Decision(Result.DENY, Reason.SECOND_FACTOR_FAILED)
    if student_inside:
        return Decision(Result.DENY, Reason.ALREADY_INSIDE)
    return Decision(Result.ALLOW, Reason.OK)


def student_exit(*, credential_found: bool) -> Decision:
    """Single factor. Anyone we can identify may leave, whatever their status,
    so nobody is ever trapped inside. (Policy to confirm with the university.)"""
    if not credential_found:
        return Decision(Result.DENY, Reason.UNKNOWN_CREDENTIAL)
    return Decision(Result.ALLOW, Reason.OK)


def vehicle(*, found: bool, vehicle_status: str | None, owner_status: str | None) -> Decision:
    if not found:
        return Decision(Result.REFER, Reason.VEHICLE_UNREGISTERED)
    if vehicle_status != "active" or owner_status != "active":
        return Decision(Result.REFER, Reason.VEHICLE_INACTIVE)
    return Decision(Result.ALLOW, Reason.OK)


def visitor(
    *, found: bool, valid_from: datetime | None, valid_until: datetime | None, now: datetime
) -> Decision:
    if not found or valid_from is None or valid_until is None:
        return Decision(Result.DENY, Reason.VISITOR_UNKNOWN)
    if now < valid_from:
        return Decision(Result.DENY, Reason.VISITOR_NOT_YET_VALID)
    if now > valid_until:
        return Decision(Result.DENY, Reason.VISITOR_EXPIRED)
    return Decision(Result.ALLOW, Reason.OK)
'''
FILES['backend/app/deps.py'] = r'''from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Gate
from .security import hash_secret


def authenticate_gate(
    x_gate_key: str = Header(...), db: Session = Depends(get_db)
) -> Gate:
    gate = db.scalar(
        select(Gate).where(Gate.api_key_hash == hash_secret(x_gate_key, settings.credential_pepper))
    )
    if gate is None:
        raise HTTPException(status_code=401, detail="invalid gate key")
    gate.last_seen_at = datetime.now(timezone.utc)  # heartbeat for gate health
    return gate
'''
FILES['backend/app/main.py'] = r'''from fastapi import FastAPI

from .routers import access, auth, enrollment, health, registration, visitors

app = FastAPI(title="Campus Gate Entry System")
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(enrollment.router)
app.include_router(access.router)
app.include_router(registration.router)
app.include_router(visitors.router)
'''
FILES['backend/app/models.py'] = r'''from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("status in ('active','suspended','revoked')", name="ck_students_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")
    inside: Mapped[bool] = mapped_column(Boolean, default=False)  # powers passback rule
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credentials: Mapped[list["Credential"]] = relationship(back_populates="student")
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="student")


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint("type in ('card','face','fingerprint')", name="ck_credentials_type"),
        UniqueConstraint("type", "template_hash", name="uq_credentials_type_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    # Hash of the card UID, or a reference to the encrypted biometric template.
    # Never a raw photo or raw fingerprint image.
    template_hash: Mapped[str] = mapped_column(String(128), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped[Student] = relationship(back_populates="credentials")


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("status in ('active','suspended','revoked')", name="ck_vehicles_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    plate: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # normalised
    status: Mapped[str] = mapped_column(String(16), default="active")

    student: Mapped[Student] = relationship(back_populates="vehicles")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('admin','registrar','guard')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    role: Mapped[str] = mapped_column(String(16))
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    registered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    full_name: Mapped[str] = mapped_column(String(200))
    id_number: Mapped[str] = mapped_column(String(64))
    host: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(300))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Gate(Base):
    __tablename__ = "gates"
    __table_args__ = (
        CheckConstraint("kind in ('student','vehicle')", name="ck_gates_kind"),
        CheckConstraint("direction in ('entry','exit')", name="ck_gates_direction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(16))
    api_key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessEvent(Base):
    """One row per access attempt. Append-only (enforced by a DB trigger)."""

    __tablename__ = "access_events"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(credential_id, vehicle_id, visitor_id) <= 1", name="ck_event_one_subject"
        ),
        CheckConstraint("result in ('allow','deny','refer_to_guard')", name="ck_event_result"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.id"), index=True)
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("credentials.id"))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    visitor_id: Mapped[int | None] = mapped_column(ForeignKey("visitors.id"))
    result: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(48))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AuditLog(Base):
    """Administrative actions and guard overrides. Append-only (DB trigger)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
'''
FILES['backend/app/routers/__init__.py'] = r''''''
FILES['backend/app/routers/access.py'] = r'''import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import decision
from ..config import settings
from ..db import get_db, get_redis
from ..deps import authenticate_gate
from ..models import AccessEvent, Credential, Gate, Student, Vehicle, Visitor
from ..security import hash_secret, normalise_plate

router = APIRouter(prefix="/api/v1/access", tags=["access"])


class CheckRequest(BaseModel):
    card_uid: str | None = None
    plate: str | None = None
    visitor_token: str | None = None
    # Biometric matching happens on the gate device; it reports the outcome.
    second_factor_type: Literal["face", "fingerprint"] | None = None
    second_factor_matched: bool = False
    liveness_passed: bool = False  # required for face

    @model_validator(mode="after")
    def exactly_one_subject(self):
        if sum(x is not None for x in (self.card_uid, self.plate, self.visitor_token)) != 1:
            raise ValueError("send exactly one of card_uid, plate, visitor_token")
        return self


class CheckResponse(BaseModel):
    result: str
    reason: str
    event_id: int


@router.post("/check", response_model=CheckResponse)
def check(req: CheckRequest, gate: Gate = Depends(authenticate_gate), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    pepper = settings.credential_pepper
    ids: dict[str, int | None] = {"credential_id": None, "vehicle_id": None, "visitor_id": None}
    student: Student | None = None

    if gate.kind == "vehicle":
        if req.plate is None:
            raise HTTPException(400, "vehicle gates accept plate only")
        v = db.scalar(select(Vehicle).where(Vehicle.plate == normalise_plate(req.plate)))
        owner = db.get(Student, v.student_id) if v else None
        d = decision.vehicle(
            found=v is not None,
            vehicle_status=v.status if v else None,
            owner_status=owner.status if owner else None,
        )
        ids["vehicle_id"] = v.id if v else None

    elif req.visitor_token is not None:
        vis = db.scalar(
            select(Visitor).where(Visitor.token_hash == hash_secret(req.visitor_token, pepper))
        )
        d = decision.visitor(
            found=vis is not None,
            valid_from=vis.valid_from if vis else None,
            valid_until=vis.valid_until if vis else None,
            now=now,
        )
        ids["visitor_id"] = vis.id if vis else None

    elif req.card_uid is not None:
        cred = db.scalar(
            select(Credential).where(
                Credential.type == "card", Credential.template_hash == hash_secret(req.card_uid, pepper)
            )
        )
        if cred is not None:
            # Row lock so two simultaneous taps cannot both pass the passback rule.
            student = db.scalar(select(Student).where(Student.id == cred.student_id).with_for_update())
            ids["credential_id"] = cred.id

        if gate.direction == "exit":
            d = decision.student_exit(credential_found=cred is not None)
        else:
            second_ok = req.second_factor_matched and (
                req.second_factor_type != "face" or req.liveness_passed
            )
            d = decision.student_entry(
                credential_found=cred is not None,
                credential_revoked=bool(cred and cred.revoked_at),
                student_status=student.status if student else None,
                student_inside=bool(student and student.inside),
                second_factor_ok=second_ok and req.second_factor_type is not None,
            )

        if d.result == decision.Result.ALLOW and student is not None:
            student.inside = gate.direction == "entry"
    else:
        raise HTTPException(400, "student gates accept card_uid or visitor_token")

    event = AccessEvent(gate_id=gate.id, result=d.result.value, reason=d.reason.value, **ids)
    db.add(event)
    db.commit()

    try:  # dashboard feed; a Redis outage must never block a gate decision
        get_redis().publish(
            "gate_events",
            json.dumps(
                {"event_id": event.id, "gate": gate.name, "result": d.result.value, "reason": d.reason.value}
            ),
        )
    except Exception:
        pass

    return CheckResponse(result=d.result.value, reason=d.reason.value, event_id=event.id)
'''
FILES['backend/app/routers/auth.py'] = r'''from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import DUMMY_HASH, create_token, verify_password
from ..config import settings
from ..db import get_db, get_redis
from ..models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

MAX_FAILS = 5
LOCK_SECONDS = 900


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    key = f"login-fails:{email}"
    r = get_redis()
    try:
        if int(r.get(key) or 0) >= MAX_FAILS:
            raise HTTPException(429, "too many attempts, try again later")
    except HTTPException:
        raise
    except Exception:  # Redis down: skip rate limit rather than lock everyone out
        r = None

    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(user.password_hash if user else DUMMY_HASH, req.password)
    if not (user and user.active and ok):
        if r is not None:
            try:
                r.incr(key)
                r.expire(key, LOCK_SECONDS)
            except Exception:
                pass
        raise HTTPException(401, "invalid credentials")

    if r is not None:
        try:
            r.delete(key)
        except Exception:
            pass
    return {
        "access_token": create_token(user.id, user.role, settings.jwt_secret),
        "token_type": "bearer",
        "role": user.role,
        "name": user.name,
    }
'''
FILES['backend/app/routers/enrollment.py'] = r'''from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, get_redis
from ..models import AuditLog, Student
from ..security import verify_enrollment

router = APIRouter(prefix="/api/v1/enrollment", tags=["enrollment"])


class StudentPush(BaseModel):
    student_no: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=200)
    status: Literal["active", "suspended", "revoked"]


@router.post("/students")
async def push_student(
    request: Request,
    x_timestamp: str = Header(...),
    x_nonce: str = Header(...),
    x_signature: str = Header(...),
    db: Session = Depends(get_db),
):
    """Called by the university registration system. Signed, replay-protected, idempotent."""
    body = await request.body()
    if not verify_enrollment(
        settings.enrollment_shared_secret,
        x_timestamp,
        x_nonce,
        body,
        x_signature,
        settings.enrollment_max_skew_seconds,
    ):
        raise HTTPException(status_code=401, detail="bad signature or stale timestamp")

    r = get_redis()
    ttl = settings.enrollment_max_skew_seconds * 2
    if not r.set(f"enroll-nonce:{x_nonce}", "1", nx=True, ex=ttl):
        raise HTTPException(status_code=409, detail="replayed request")

    payload = StudentPush.model_validate_json(body)
    student = db.scalar(select(Student).where(Student.student_no == payload.student_no))
    created = student is None
    if created:
        student = Student(student_no=payload.student_no, full_name=payload.full_name, status=payload.status)
        db.add(student)
    else:
        student.full_name = payload.full_name
        student.status = payload.status

    db.add(
        AuditLog(
            action="enrollment.upsert",
            detail={"student_no": payload.student_no, "status": payload.status, "created": created},
        )
    )
    db.commit()

    # Tell gates immediately about blocking changes (urgent revocation path).
    if payload.status != "active":
        r.publish("revocations", payload.student_no)

    return {"student_no": payload.student_no, "status": payload.status, "created": created}
'''
FILES['backend/app/routers/health.py'] = r'''from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db, get_redis

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    get_redis().ping()
    return {"status": "ok"}
'''
FILES['backend/app/routers/registration.py'] = r'''from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import audit
from ..auth import require_role
from ..config import settings
from ..db import get_db
from ..models import Credential, Student, User, Vehicle
from ..security import hash_secret, normalise_plate

router = APIRouter(prefix="/api/v1/registration", tags=["registration"])
registrar = require_role("registrar", "admin")


class CredentialIn(BaseModel):
    type: Literal["card", "face", "fingerprint"]
    # card: the card UID. face/fingerprint: the template reference ID issued by the
    # enrolment device. Never send raw photos or raw fingerprint images here.
    value: str = Field(min_length=1, max_length=256)
    consent_given: bool


class VehicleIn(BaseModel):
    plate: str = Field(min_length=2, max_length=16)


def _student(db: Session, student_no: str) -> Student:
    s = db.scalar(select(Student).where(Student.student_no == student_no))
    if s is None:
        raise HTTPException(404, "student not found (must be pushed by the registration system first)")
    return s


@router.post("/students/{student_no}/credentials", status_code=201)
def add_credential(
    student_no: str, body: CredentialIn, db: Session = Depends(get_db), user: User = Depends(registrar)
):
    if not body.consent_given:
        raise HTTPException(400, "consent is required before registering credentials")
    s = _student(db, student_no)
    if s.status != "active":
        raise HTTPException(409, f"student is {s.status}")

    h = hash_secret(body.value, settings.credential_pepper)
    if db.scalar(select(Credential).where(Credential.type == body.type, Credential.template_hash == h)):
        raise HTTPException(409, "this credential is already registered")

    cred = Credential(student_id=s.id, type=body.type, template_hash=h)
    db.add(cred)
    if s.consent_recorded_at is None:
        s.consent_recorded_at = func.now()
    db.flush()
    audit(db, user, "credential.register", {"student_no": student_no, "type": body.type, "credential_id": cred.id})
    db.commit()
    return {"credential_id": cred.id, "type": cred.type}


@router.delete("/credentials/{credential_id}")
def revoke_credential(credential_id: int, db: Session = Depends(get_db), user: User = Depends(registrar)):
    cred = db.get(Credential, credential_id)
    if cred is None:
        raise HTTPException(404, "credential not found")
    if cred.revoked_at is None:
        cred.revoked_at = func.now()
        audit(db, user, "credential.revoke", {"credential_id": credential_id, "student_id": cred.student_id})
        db.commit()
    return {"credential_id": credential_id, "revoked": True}


@router.post("/students/{student_no}/vehicles", status_code=201)
def add_vehicle(
    student_no: str, body: VehicleIn, db: Session = Depends(get_db), user: User = Depends(registrar)
):
    s = _student(db, student_no)
    plate = normalise_plate(body.plate)
    if len(plate) < 2:
        raise HTTPException(400, "invalid plate")
    if db.scalar(select(Vehicle).where(Vehicle.plate == plate)):
        raise HTTPException(409, "plate already registered")
    v = Vehicle(student_id=s.id, plate=plate, status="active")
    db.add(v)
    db.flush()
    audit(db, user, "vehicle.register", {"student_no": student_no, "plate": plate, "vehicle_id": v.id})
    db.commit()
    return {"vehicle_id": v.id, "plate": plate}
'''
FILES['backend/app/routers/visitors.py'] = r'''import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..auth import require_role
from ..config import settings
from ..db import get_db
from ..models import User, Visitor
from ..security import hash_secret

router = APIRouter(prefix="/api/v1/visitors", tags=["visitors"])
guard = require_role("guard", "admin")

MAX_PASS_HOURS = 24  # policy default; confirm with the university


class VisitorIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    id_number: str = Field(min_length=1, max_length=64)
    host: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=300)
    valid_from: datetime | None = None  # defaults to now
    valid_until: datetime


@router.post("", status_code=201)
def register_visitor(body: VisitorIn, db: Session = Depends(get_db), user: User = Depends(guard)):
    now = datetime.now(timezone.utc)
    start = body.valid_from or now
    if start.tzinfo is None or body.valid_until.tzinfo is None:
        raise HTTPException(400, "datetimes must include a timezone")
    if body.valid_until <= start:
        raise HTTPException(400, "valid_until must be after valid_from")
    if body.valid_until - start > timedelta(hours=MAX_PASS_HOURS):
        raise HTTPException(400, f"passes are limited to {MAX_PASS_HOURS} hours")

    token = secrets.token_urlsafe(24)  # put this in the QR code; shown only once
    v = Visitor(
        registered_by=user.id,
        full_name=body.full_name,
        id_number=body.id_number,
        host=body.host,
        purpose=body.purpose,
        token_hash=hash_secret(token, settings.credential_pepper),
        valid_from=start,
        valid_until=body.valid_until,
    )
    db.add(v)
    db.flush()
    audit(db, user, "visitor.register", {"visitor_id": v.id, "host": body.host, "valid_until": body.valid_until.isoformat()})
    db.commit()
    return {"visitor_id": v.id, "qr_token": token, "valid_from": start, "valid_until": body.valid_until}


@router.get("/active")
def active_visitors(db: Session = Depends(get_db), user: User = Depends(guard)):
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(Visitor).where(Visitor.valid_from <= now, Visitor.valid_until >= now)).all()
    return [
        {"id": v.id, "full_name": v.full_name, "host": v.host, "valid_until": v.valid_until}
        for v in rows
    ]
'''
FILES['backend/app/security.py'] = r'''"""Pure helpers (no settings imports) so they are trivially unit-testable."""
import hashlib
import hmac
import re
import time


def hash_secret(value: str, pepper: str) -> str:
    """Keyed hash for card UIDs, plates, visitor tokens and gate keys."""
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def normalise_plate(plate: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", plate.upper())


def sign_enrollment(secret: str, timestamp: str, nonce: str, body: bytes) -> str:
    msg = timestamp.encode() + b"." + nonce.encode() + b"." + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_enrollment(
    secret: str,
    timestamp: str,
    nonce: str,
    body: bytes,
    signature: str,
    max_skew_seconds: int,
    now: float | None = None,
) -> bool:
    try:
        ts = float(timestamp)
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - ts) > max_skew_seconds:
        return False
    expected = sign_enrollment(secret, timestamp, nonce, body)
    return hmac.compare_digest(expected, signature)
'''
FILES['backend/app/seed.py'] = r'''"""Create the five access points from the spec and print their API keys ONCE.

Run:  docker compose exec api python -m app.seed
"""
import secrets

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Gate
from .security import hash_secret

GATES = [
    ("student-entry-1", "student", "entry"),
    ("student-entry-2", "student", "entry"),
    ("student-exit-1", "student", "exit"),
    ("vehicle-entry-1", "vehicle", "entry"),
    ("vehicle-exit-1", "vehicle", "exit"),
]


def main() -> None:
    with SessionLocal() as db:
        for name, kind, direction in GATES:
            if db.scalar(select(Gate).where(Gate.name == name)):
                print(f"{name}: already exists (key not shown again)")
                continue
            key = secrets.token_urlsafe(32)
            db.add(
                Gate(name=name, kind=kind, direction=direction,
                     api_key_hash=hash_secret(key, settings.credential_pepper))
            )
            print(f"{name}: X-Gate-Key = {key}")
        db.commit()


if __name__ == "__main__":
    main()
'''
FILES['backend/app/seed_admin.py'] = r'''"""Create the first admin user interactively.

Run:  docker compose exec api python -m app.seed_admin
"""
import getpass

from sqlalchemy import select

from .auth import hash_password
from .db import SessionLocal
from .models import User


def main() -> None:
    email = input("Admin email: ").strip().lower()
    name = input("Full name: ").strip()
    password = getpass.getpass("Password (min 12 chars): ")
    if len(password) < 12:
        raise SystemExit("Password too short.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("User already exists.")
        db.add(User(name=name, email=email, role="admin", password_hash=hash_password(password)))
        db.commit()
    print("Admin created.")


if __name__ == "__main__":
    main()
'''
FILES['backend/requirements.txt'] = r'''fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
sqlalchemy>=2.0,<2.1
alembic>=1.13,<2
psycopg[binary]>=3.2,<4
redis>=5,<6
pydantic-settings>=2.4,<3
argon2-cffi>=23.1
pyjwt>=2.9,<3
pytest>=8,<9
httpx>=0.27,<1
'''
FILES['backend/tests/__init__.py'] = r''''''
FILES['backend/tests/test_auth.py'] = r'''import time

import jwt

from app.auth import create_token, decode_token, hash_password, verify_password

SECRET = "x" * 32


def test_password_roundtrip():
    h = hash_password("correct horse battery")
    assert verify_password(h, "correct horse battery")
    assert not verify_password(h, "wrong")


def test_verify_handles_garbage_hash():
    assert not verify_password("not-a-hash", "anything")


def test_token_roundtrip():
    claims = decode_token(create_token(7, "guard", SECRET), SECRET)
    assert claims["sub"] == "7" and claims["role"] == "guard"


def test_wrong_secret_rejected():
    assert decode_token(create_token(7, "guard", SECRET), "y" * 32) is None


def test_expired_token_rejected():
    tok = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) - 10}, SECRET, algorithm="HS256")
    assert decode_token(tok, SECRET) is None


def test_none_algorithm_rejected():
    forged = jwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) + 600}, None, algorithm="none")
    assert decode_token(forged, SECRET) is None
'''
FILES['backend/tests/test_decision.py'] = r'''from datetime import datetime, timedelta, timezone

from app import decision as d
from app.decision import Reason, Result

NOW = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)


def entry(**over):
    base = dict(
        credential_found=True,
        credential_revoked=False,
        student_status="active",
        student_inside=False,
        second_factor_ok=True,
    )
    base.update(over)
    return d.student_entry(**base)


def test_valid_student_enters():
    assert entry() == d.Decision(Result.ALLOW, Reason.OK)


def test_unknown_card_denied():
    assert entry(credential_found=False).reason == Reason.UNKNOWN_CREDENTIAL


def test_revoked_credential_denied():
    assert entry(credential_revoked=True).reason == Reason.CREDENTIAL_REVOKED


def test_suspended_and_revoked_students_denied():
    for status in ("suspended", "revoked"):
        out = entry(student_status=status)
        assert out.result == Result.DENY and out.reason == Reason.STUDENT_NOT_ACTIVE


def test_lent_or_cloned_card_fails_second_factor():
    assert entry(second_factor_ok=False).reason == Reason.SECOND_FACTOR_FAILED


def test_passback_blocks_second_entry():
    assert entry(student_inside=True).reason == Reason.ALREADY_INSIDE


def test_exit_allowed_for_known_credential_even_if_suspended():
    assert d.student_exit(credential_found=True).result == Result.ALLOW


def test_exit_unknown_credential_denied():
    assert d.student_exit(credential_found=False).result == Result.DENY


def test_registered_vehicle_allowed():
    out = d.vehicle(found=True, vehicle_status="active", owner_status="active")
    assert out.result == Result.ALLOW


def test_unregistered_vehicle_referred_to_guard():
    out = d.vehicle(found=False, vehicle_status=None, owner_status=None)
    assert out == d.Decision(Result.REFER, Reason.VEHICLE_UNREGISTERED)


def test_vehicle_of_revoked_student_referred():
    out = d.vehicle(found=True, vehicle_status="active", owner_status="revoked")
    assert out.reason == Reason.VEHICLE_INACTIVE


def test_visitor_window():
    f, u = NOW - timedelta(hours=1), NOW + timedelta(hours=1)
    assert d.visitor(found=True, valid_from=f, valid_until=u, now=NOW).result == Result.ALLOW
    early = d.visitor(found=True, valid_from=NOW + timedelta(minutes=5), valid_until=u, now=NOW)
    assert early.reason == Reason.VISITOR_NOT_YET_VALID
    late = d.visitor(found=True, valid_from=f, valid_until=NOW - timedelta(seconds=1), now=NOW)
    assert late.reason == Reason.VISITOR_EXPIRED


def test_unknown_visitor_denied():
    out = d.visitor(found=False, valid_from=None, valid_until=None, now=NOW)
    assert out.reason == Reason.VISITOR_UNKNOWN
'''
FILES['backend/tests/test_security.py'] = r'''from app.security import hash_secret, normalise_plate, sign_enrollment, verify_enrollment

SECRET = "s3cret"
BODY = b'{"student_no":"S1","full_name":"A B","status":"active"}'


def test_valid_signature_accepted():
    sig = sign_enrollment(SECRET, "1000", "n1", BODY)
    assert verify_enrollment(SECRET, "1000", "n1", BODY, sig, 300, now=1100)


def test_tampered_body_rejected():
    sig = sign_enrollment(SECRET, "1000", "n1", BODY)
    assert not verify_enrollment(SECRET, "1000", "n1", BODY + b" ", sig, 300, now=1100)


def test_wrong_secret_rejected():
    sig = sign_enrollment("other", "1000", "n1", BODY)
    assert not verify_enrollment(SECRET, "1000", "n1", BODY, sig, 300, now=1100)


def test_stale_timestamp_rejected():
    sig = sign_enrollment(SECRET, "1000", "n1", BODY)
    assert not verify_enrollment(SECRET, "1000", "n1", BODY, sig, 300, now=2000)


def test_garbage_timestamp_rejected():
    assert not verify_enrollment(SECRET, "abc", "n1", BODY, "x", 300, now=1)


def test_hash_is_keyed_and_stable():
    assert hash_secret("04A1B2", "p1") == hash_secret("04A1B2", "p1")
    assert hash_secret("04A1B2", "p1") != hash_secret("04A1B2", "p2")


def test_plate_normalisation():
    assert normalise_plate("b 123-abc") == "B123ABC"
'''
FILES['docker-compose.yml'] = r'''services:
  db:
    image: postgres:16
    env_file: .env
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app

volumes:
  pgdata:
'''


def make_env(example: str) -> str:
    pw = secrets.token_hex(16)
    text = example.replace("POSTGRES_PASSWORD=change-me", f"POSTGRES_PASSWORD={pw}")
    text = text.replace("gate:change-me@", f"gate:{pw}@")
    return re.sub(r"change-me-long-random", lambda m: secrets.token_hex(32), text)


def main() -> None:
    base = Path.cwd()
    for rel, content in FILES.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print("created", rel)
    env = base / ".env"
    if env.exists():
        print(".env already exists - left untouched")
    else:
        with open(env, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(make_env(FILES[".env.example"]))
        print("created .env with generated secrets (never commit it)")
    print("\nDone. Next: docker compose up --build")


if __name__ == "__main__":
    main()
