import os, json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import DEMO_DATE
from .db import get_db
from . import models as m
from .deps import require
from .services import notify, now_lk, next_operating_date

router = APIRouter(prefix="/api/store")
dep = require("store")
ENFORCE_CUTOFF = os.getenv("ENFORCE_CUTOFF", "0") == "1"     # off by default so judges can order at any hour


def cutoff_info():
    n = now_lk()
    return dict(cutoff="16:00", now=n.strftime("%H:%M"), after_cutoff=n.hour >= 16, enforced=ENFORCE_CUTOFF)


@router.get("/outlet")
def outlet(user=Depends(dep), db: Session = Depends(get_db)):
    o = db.get(m.Outlet, user.outlet_id)
    return dict(outlet_id=o.outlet_id, brand=o.brand, district=o.district, depot=o.depot, dock_type=o.dock_type,
                window=f"{o.window_open_time}-{o.window_close_time}", demo_date=DEMO_DATE, **cutoff_info())


class OrderBody(BaseModel):
    temp_requirement: str = "ambient"
    order_units: int
    order_weight_kg: float | None = None      # the order form only asks for quantities; estimated per brand if omitted
    order_volume_m3: float | None = None
    delivery_date: str | None = None
    items: list[dict] | None = None           # [{name, qty}] shown again on the receipt screen


# planning estimates per unit when the form gives quantities only
PER_UNIT = {"Fresh": (14.0, 0.125), "Style": (4.0, 0.11), "Tech": (35.0, 0.12)}


@router.post("/orders")
def place(body: OrderBody, user=Depends(dep), db: Session = Depends(get_db)):
    o = db.get(m.Outlet, user.outlet_id)
    if body.temp_requirement not in ("ambient", "chilled") or (body.temp_requirement == "chilled" and o.brand != "Fresh"):
        raise HTTPException(422, "Only Fresh outlets can order chilled goods.")
    kg, m3 = PER_UNIT.get(o.brand, (14.0, 0.125))
    weight = body.order_weight_kg if body.order_weight_kg else round(body.order_units * kg, 1)
    volume = body.order_volume_m3 if body.order_volume_m3 else round(body.order_units * m3, 2)
    if body.order_units < 1 or weight <= 0 or volume <= 0:
        raise HTTPException(422, "Add at least one item to the order.")
    after = cutoff_info()["after_cutoff"] and ENFORCE_CUTOFF
    date = body.delivery_date or DEMO_DATE
    published = db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == o.depot, m.Plan.status == "published"))
    if published or after:
        date, after = next_operating_date(db, date), True
    n = db.scalar(select(func.count()).select_from(m.Order)) + 1
    ref = f"WP{date.replace('-', '')}-{n:03d}"
    order = m.Order(order_ref=ref, outlet_id=o.outlet_id, brand=o.brand, district=o.district, depot=o.depot,
                    delivery_date=date, temp_requirement=body.temp_requirement, order_units=body.order_units,
                    order_weight_kg=weight, order_volume_m3=volume, days_since_last_served=1,
                    items_json=json.dumps(body.items) if body.items else None)
    db.add(order)
    notify(db, "dispatcher", "order", f"New confirmed order {ref} from {o.outlet_id} ({o.brand}, {body.temp_requirement}) for {date}.")
    db.commit()
    msg = (f"Order {ref} received and confirmed for {date}. " +
           ("It arrived after the 4 PM cutoff / the day is already planned, so it joins the next run. " if after else
            "You will get an expected arrival time once the plan is published."))
    return dict(order_ref=ref, delivery_date=date, confirmed=True, after_cutoff=after, message=msg)


@router.get("/orders")
def orders(user=Depends(dep), db: Session = Depends(get_db)):
    out = []
    for o in db.scalars(select(m.Order).where(m.Order.outlet_id == user.outlet_id).order_by(m.Order.id.desc()).limit(30)):
        stop = db.scalar(select(m.TripStop).where(m.TripStop.order_id == o.id).order_by(m.TripStop.id.desc()))
        d = db.scalar(select(m.Deferral).where(m.Deferral.order_id == o.id).order_by(m.Deferral.id.desc()))
        rc = db.scalar(select(m.Receipt).where(m.Receipt.order_id == o.id))
        trip = stop.trip if stop else None
        published = bool(trip and db.get(m.Plan, trip.plan_id).status == "published")
        out.append(dict(
            id=o.id, order_ref=o.order_ref, delivery_date=o.delivery_date, temp=o.temp_requirement, units=o.order_units,
            volume_m3=o.order_volume_m3, weight_kg=o.order_weight_kg, status=o.status,
            items=json.loads(o.items_json) if o.items_json else [dict(name="Units", qty=o.order_units)],
            outlet_id=o.outlet_id, brand=o.brand,
            eta=stop.eta if stop and published and stop.status != "cancelled" else None,
            window=stop.window if stop and published else None, vehicle_id=trip.vehicle_id if published else None,
            stop_status=stop.status if stop and published else None, delivered_at=stop.time_in if stop else None,
            deferral=dict(reason=d.reason_text, rescheduled_for=d.rescheduled_for) if d and o.status == "deferred" else None,
            receipt=dict(status=rc.status, note=rc.note) if rc else None))
    return out


class ReceiptBody(BaseModel):
    status: str       # confirmed | issue
    note: str | None = None


@router.post("/orders/{order_id}/receipt")
def receipt(order_id: int, body: ReceiptBody, user=Depends(dep), db: Session = Depends(get_db)):
    o = db.get(m.Order, order_id)
    if not o or o.outlet_id != user.outlet_id:
        raise HTTPException(404, "Order not found")
    if o.status != "delivered":
        raise HTTPException(409, "You can confirm receipt once the driver has recorded the delivery.")
    if body.status not in ("confirmed", "issue") or (body.status == "issue" and not (body.note or "").strip()):
        raise HTTPException(422, "Describe the issue so the dispatcher can act on it.")
    db.add(m.Receipt(order_id=o.id, status=body.status, note=body.note))
    o.status = "received" if body.status == "confirmed" else "issue"
    if body.status == "issue":
        notify(db, "dispatcher", "issue", f"Receipt issue from {o.outlet_id} on {o.order_ref}: {body.note}")
    db.commit()
    return dict(status=o.status)
