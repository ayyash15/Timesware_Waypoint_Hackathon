from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import DEMO_DATE
from .db import get_db
from . import models as m
from .deps import require
from .services import notify, trip_view, parse_ts

router = APIRouter(prefix="/api/driver")
dep = require("driver")
FINAL = ("delivered", "partial", "failed")


@router.get("/vehicles")
def vehicles(date: str = DEMO_DATE, user=Depends(dep), db: Session = Depends(get_db)):
    q = (select(m.Trip.vehicle_id).join(m.Plan, m.Plan.id == m.Trip.plan_id)
         .where(m.Plan.plan_date == date, m.Plan.status == "published", m.Trip.depot == user.depot).distinct())
    active = db.scalars(q.where(m.Trip.status.in_(("ready", "departed")))).all()     # released by the loader / on the road
    return dict(default=user.vehicle_id, with_routes=sorted(db.scalars(q).all()), active=sorted(active))


@router.get("/route")
def route(date: str = DEMO_DATE, vehicle_id: str | None = None, user=Depends(dep), db: Session = Depends(get_db)):
    vid = vehicle_id or user.vehicle_id
    trips = db.scalars(select(m.Trip).join(m.Plan, m.Plan.id == m.Trip.plan_id)
                       .where(m.Plan.plan_date == date, m.Plan.status == "published", m.Trip.vehicle_id == vid)
                       .order_by(m.Trip.trip_no)).all()
    return dict(vehicle_id=vid, date=date, trips=[trip_view(t) for t in trips])


@router.post("/trips/{trip_id}/depart")
def depart(trip_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    t = db.get(m.Trip, trip_id)
    if not t:
        raise HTTPException(404, "Trip not found")
    if t.status != "ready":
        raise HTTPException(409, "The loader has not released this vehicle yet." if t.status in ("planned", "loading")
                            else f"Trip is already {t.status}.")
    t.status = "departed"
    for s in t.stops:
        if s.status == "pending":
            s.order.status = "in_transit"
    notify(db, "dispatcher", "depart", f"{t.vehicle_id} departed on trip {t.trip_no} to {t.district}.")
    db.commit()
    return dict(status=t.status)


class Event(BaseModel):
    client_uuid: str
    stop_id: int
    status: str                       # delivered | partial | failed
    time_in: str | None = None
    time_out: str | None = None
    note: str | None = None
    pod_photo: str | None = None
    recorded_at: str | None = None    # device time when the driver pressed save (ISO)


class SyncBody(BaseModel):
    events: list[Event]


def _apply(db, s: m.TripStop, ev: Event, rec: datetime, note: str | None = None):
    s.status, s.time_in, s.time_out, s.note = ev.status, ev.time_in, ev.time_out, ev.note
    s.pod_photo, s.client_uuid, s.recorded_at, s.synced_at = ev.pod_photo, ev.client_uuid, rec, datetime.utcnow()
    if note:
        s.conflict_note = note
    o = s.order
    o.status = "failed" if ev.status == "failed" else "delivered"
    if ev.status == "failed":
        notify(db, "dispatcher", "failed", f"Delivery failed at {o.outlet_id} ({o.order_ref}): {ev.note or 'no note'}")
        notify(db, "store", "failed", f"We could not deliver order {o.order_ref}: {ev.note or 'see dispatcher'}.", outlet_id=o.outlet_id)
    else:
        notify(db, "store", "delivered", f"Order {o.order_ref} was delivered at {ev.time_in or 'today'}"
               f"{' (partial)' if ev.status == 'partial' else ''}. Please confirm what you received.", outlet_id=o.outlet_id)
    trip = s.trip
    if all(x.status not in ("pending",) for x in trip.stops):
        trip.status = "completed"
        notify(db, "dispatcher", "completed", f"{trip.vehicle_id} completed trip {trip.trip_no} ({trip.district}).")


@router.post("/sync")
def sync(body: SyncBody, user=Depends(dep), db: Session = Depends(get_db)):
    """Idempotent. The app queues every outcome locally and posts the queue whenever it has signal."""
    results = []
    for ev in body.events:
        def res(result, msg=""):
            results.append(dict(client_uuid=ev.client_uuid, stop_id=ev.stop_id, result=result, message=msg))
        if db.scalar(select(m.TripStop).where(m.TripStop.client_uuid == ev.client_uuid)):
            res("duplicate", "Already received")
            continue
        s = db.get(m.TripStop, ev.stop_id)
        if not s or ev.status not in FINAL:
            res("rejected", "Unknown stop or outcome")
            continue
        if ev.status in ("delivered", "partial") and not ev.pod_photo:
            res("rejected", "Proof of delivery photo is required")
            continue
        if ev.status in ("failed", "partial") and not (ev.note or "").strip():
            res("rejected", "A note is required for failed or partial deliveries")
            continue
        rec = parse_ts(ev.recorded_at)
        if s.status == "cancelled":
            d = db.scalar(select(m.Deferral).where(m.Deferral.order_id == s.order_id).order_by(m.Deferral.created_at.desc()))
            if d and rec < d.created_at:
                # driver delivered before the dispatcher's change reached the phone -> driver's timestamp wins
                db.delete(d)
                _apply(db, s, ev, rec, f"Recorded offline at {rec:%H:%M} UTC, before the dispatcher deferral at "
                                       f"{d.created_at:%H:%M} UTC. Driver record kept.")
                notify(db, "dispatcher", "conflict", f"Sync conflict resolved at {s.order.outlet_id}: delivery was recorded "
                       f"before your deferral, so the delivery stands.")
                res("applied", "Your delivery was recorded before the stop was cancelled. It stands.")
            else:
                s.conflict_note = "Dispatcher cancelled this stop before the driver recorded it. Record not applied."
                notify(db, "dispatcher", "conflict", f"Driver record at {s.order.outlet_id} arrived after your deferral and was not applied.")
                res("rejected", "This stop was cancelled by the dispatcher before you recorded it.")
            continue
        if s.status != "pending":
            s.conflict_note = f"A second record arrived for a stop already marked {s.status}. First record kept."
            notify(db, "dispatcher", "conflict", f"Duplicate record for {s.order.outlet_id}; first record kept.")
            res("conflict", "This stop already has an outcome. First record kept.")
            continue
        _apply(db, s, ev, rec)
        res("applied")
    db.commit()
    return dict(results=results)


class IssueBody(BaseModel):
    trip_id: int
    stop_id: int | None = None
    note: str


@router.post("/issues")
def issue(body: IssueBody, user=Depends(dep), db: Session = Depends(get_db)):
    t = db.get(m.Trip, body.trip_id)
    if not t or not body.note.strip():
        raise HTTPException(422, "Trip and note are required")
    where = f" at {db.get(m.TripStop, body.stop_id).order.outlet_id}" if body.stop_id else ""
    notify(db, "dispatcher", "issue", f"Driver issue on {t.vehicle_id}{where}: {body.note.strip()}")
    db.commit()
    return dict(ok=True)
