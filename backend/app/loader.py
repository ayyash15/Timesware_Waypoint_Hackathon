from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import DEMO_DATE
from .db import get_db
from . import models as m
from .deps import require
from .services import notify, trip_view

router = APIRouter(prefix="/api/loader")
dep = require("loader")


def open_issues(db, trip_id):
    return db.scalars(select(m.LoadingIssue).where(m.LoadingIssue.trip_id == trip_id, m.LoadingIssue.resolved == False)).all()  # noqa: E712


@router.get("/trips")
def trips(date: str = DEMO_DATE, user=Depends(dep), db: Session = Depends(get_db)):
    plan = db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == user.depot,
                                          m.Plan.status == "published").order_by(m.Plan.id.desc()))
    if not plan:
        return dict(published=False, trips=[])
    out = []
    for t in db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id).order_by(m.Trip.depart_time, m.Trip.vehicle_id, m.Trip.trip_no)):
        v = trip_view(t)
        live = [s for s in v["stops"] if s["status"] != "cancelled"]
        # last stop is loaded first so the first stop comes off the truck first
        v["load_order"] = [dict(load_no=i + 1, **s) for i, s in enumerate(reversed(live))]
        v["open_issues"] = [dict(id=i.id, order_id=i.order_id, type=i.issue_type, note=i.note) for i in open_issues(db, t.id)]
        out.append(v)
    return dict(published=True, plan_date=date, trips=out)


@router.post("/trips/{trip_id}/start")
def start(trip_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    t = db.get(m.Trip, trip_id)
    if not t or t.depot != user.depot:
        raise HTTPException(404, "Trip not found")
    if t.status == "planned":
        t.status = "loading"
        db.commit()
    return dict(status=t.status)


class ReadyBody(BaseModel):
    force: bool = False


@router.post("/stops/{stop_id}/loaded")
def stop_loaded(stop_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    """The loader's "Loaded" tick for one stop. Persisted so the list survives a refresh or a hand-over."""
    s = db.get(m.TripStop, stop_id)
    if not s or s.trip.depot != user.depot:
        raise HTTPException(404, "Stop not found")
    if s.trip.status not in ("planned", "loading"):
        raise HTTPException(409, f"Trip is already {s.trip.status}.")
    s.loaded = 1
    if s.trip.status == "planned":
        s.trip.status = "loading"
    live = [x for x in s.trip.stops if x.status != "cancelled"]
    db.commit()
    return dict(trip_status=s.trip.status, all_loaded=all(x.loaded for x in live), loaded=sum(1 for x in live if x.loaded), total=len(live))


@router.post("/trips/{trip_id}/ready")
def ready(trip_id: int, body: ReadyBody = ReadyBody(), user=Depends(dep), db: Session = Depends(get_db)):
    t = db.get(m.Trip, trip_id)
    if not t or t.depot != user.depot:
        raise HTTPException(404, "Trip not found")
    if t.status not in ("planned", "loading"):
        raise HTTPException(409, f"Trip is already {t.status}.")
    issues = open_issues(db, t.id)
    if issues and not body.force:
        raise HTTPException(409, detail=dict(errors=[f"{len(issues)} unresolved loading issue(s). Confirm to release the vehicle anyway."],
                                             needs_force=True))
    t.status = "ready"
    for s in t.stops:
        if s.status == "pending":
            s.order.status = "loaded"
    notify(db, "driver", "ready", f"Trip {t.trip_no} to {t.district} is loaded and ready to depart.", vehicle_id=t.vehicle_id)
    notify(db, "dispatcher", "ready", f"{t.vehicle_id} trip {t.trip_no} ({t.district}) is loaded and ready"
           + (" with open issues." if issues else "."))
    db.commit()
    return dict(status=t.status)


class IssueBody(BaseModel):
    trip_id: int
    order_id: int
    issue_type: str          # missing | damaged | short
    note: str | None = None
    photo: str | None = None


@router.post("/issues")
def raise_issue(body: IssueBody, user=Depends(dep), db: Session = Depends(get_db)):
    t, o = db.get(m.Trip, body.trip_id), db.get(m.Order, body.order_id)
    if not t or not o or t.depot != user.depot:
        raise HTTPException(404, "Trip or order not found")
    if body.issue_type not in ("missing", "damaged", "short"):
        raise HTTPException(422, "Issue type must be missing, damaged or short")
    db.add(m.LoadingIssue(trip_id=t.id, order_id=o.id, issue_type=body.issue_type, note=body.note,
                          photo=body.photo, created_by=user.id))
    notify(db, "dispatcher", "issue", f"Loading shortfall on {t.vehicle_id} trip {t.trip_no}: {body.issue_type} items for "
           f"{o.order_ref} ({o.outlet_id}). {body.note or ''}".strip())
    notify(db, "store", "issue", f"Heads up: part of order {o.order_ref} may arrive {body.issue_type}. We are resolving it.",
           outlet_id=o.outlet_id)
    db.commit()
    return dict(ok=True)
