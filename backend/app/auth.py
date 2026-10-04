from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from .db import get_db
from . import models as m
from .deps import make_token, current_user
from .security import verify_password
from .config import DEMO_LOGIN

router = APIRouter(prefix="/api")


class Login(BaseModel):
    username: str
    password: str


def user_json(u: m.User) -> dict:
    return dict(id=u.id, username=u.username, role=u.role, name=u.display_name, depot=u.depot,
                outlet_id=u.outlet_id, vehicle_id=u.vehicle_id)


@router.post("/auth/login")
def login(body: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(m.User).where(m.User.username == body.username.strip().lower()))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return dict(token=make_token(u), user=user_json(u))


@router.get("/auth/demo")
def demo_login(role: str, db: Session = Depends(get_db)):
    """Token for the seeded account of a role. Backs the design's role-picker Home page (no login screen exists)."""
    if not DEMO_LOGIN:
        raise HTTPException(403, "Demo sign-in is disabled")
    u = db.scalar(select(m.User).where(m.User.role == role))
    if not u:
        raise HTTPException(404, "Unknown role")
    return dict(token=make_token(u), user=user_json(u))


@router.get("/me")
def me(user: m.User = Depends(current_user)):
    return user_json(user)


@router.get("/notifications")
def notifications(vehicle_id: str | None = None, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(m.Notification).where(m.Notification.role == user.role)
    if user.role == "store":
        q = q.where(m.Notification.outlet_id == user.outlet_id)
    if user.role == "driver":
        vid = vehicle_id or user.vehicle_id
        q = q.where(or_(m.Notification.vehicle_id == None, m.Notification.vehicle_id == vid))   # noqa: E711
    rows = db.scalars(q.order_by(m.Notification.id.desc()).limit(40)).all()
    return [dict(id=n.id, kind=n.kind, message=n.message, at=n.created_at.isoformat() + "Z", read=n.read) for n in rows]
