from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_role
from ..db import get_db
from ..deps import authenticate_gate
from ..models import AccessEvent, Gate, Student, User

router = APIRouter(prefix="/api/v1", tags=["monitoring"])
watch = require_role("guard", "admin")


@router.get("/events")
def recent_events(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(watch),
):
    """Newest first. Deliberately excludes names and credential details (privacy)."""
    rows = db.execute(
        select(AccessEvent, Gate.name)
        .join(Gate, Gate.id == AccessEvent.gate_id)
        .order_by(AccessEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        {"id": e.id, "gate": name, "result": e.result, "reason": e.reason, "occurred_at": e.occurred_at}
        for e, name in rows
    ]


@router.get("/gates")
def gates(db: Session = Depends(get_db), user: User = Depends(watch)):
    rows = db.scalars(select(Gate).order_by(Gate.name)).all()
    return [
        {"name": g.name, "kind": g.kind, "direction": g.direction, "last_seen_at": g.last_seen_at}
        for g in rows
    ]


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(watch)):
    on_campus = db.scalar(select(func.count()).select_from(Student).where(Student.inside.is_(True)))
    return {"on_campus": on_campus}


@router.post("/gates/heartbeat")
def heartbeat(gate: Gate = Depends(authenticate_gate), db: Session = Depends(get_db)):
    """Gate devices call this every ~30s so the dashboard can show online/offline."""
    db.commit()  # authenticate_gate already set last_seen_at
    return {"gate": gate.name}
