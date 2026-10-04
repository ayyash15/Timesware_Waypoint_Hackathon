import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import DEMO_DATE
from .db import get_db
from . import models as m
from .deps import require
from .engine import allocate, validate_plan, layout, CONSTRAINT_OF
from .services import (build_ctx, vehicles_for, order_dict, notify, trip_view, next_operating_date)

router = APIRouter(prefix="/api/dispatcher")
dep = require("dispatcher")


# ---------------- helpers ----------------
def day_orders(db, date, depot):
    return db.scalars(select(m.Order).where(m.Order.delivery_date == date, m.Order.depot == depot)
                      .order_by(m.Order.id)).all()


def get_plan(db, plan_id, depot, must_be_draft=False):
    plan = db.get(m.Plan, plan_id)
    if not plan or plan.depot != depot:
        raise HTTPException(404, "Plan not found")
    if must_be_draft and plan.status != "draft":
        raise HTTPException(409, "This plan is published and locked. Defer individual stops from the live view instead.")
    return plan


def clear_trips(db, plan):
    for t in db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id)).all():
        for s in list(t.stops):
            db.delete(s)
        db.delete(t)
    db.flush()


def write_trips(db, plan, trips, by_ref):
    for t in trips:
        tr = m.Trip(plan_id=plan.id, vehicle_id=t["vehicle_id"], trip_no=t["trip_no"], brand=t["brand"],
                    district=t["district"], depot=t["depot"], depart_time=t["depart"], minutes=t["minutes"],
                    fuel_l=t["fuel_l"], volume_m3=t["volume_m3"], weight_kg=t["weight_kg"])
        db.add(tr)
        db.flush()
        for s in t["stops"]:
            o = by_ref[s["order_ref"]]
            db.add(m.TripStop(trip_id=tr.id, order_id=o.id, seq=s["seq"], eta=s["eta"], window=s["window"]))
            o.status = "planned"
    db.flush()


def current_assignments(db, plan):
    out = []
    for t in db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id)):
        for s in t.stops:
            out.append(dict(order_ref=s.order.order_ref, vehicle_id=t.vehicle_id, trip_no=t.trip_no))
    return out


def explanation(d: m.Deferral) -> str:
    """Plain-English explanation for the dispatcher: what blocked it, and why it was this order."""
    o = d.order
    bits = [d.reason_text]
    if d.decided_by != "engine":
        bits.append(f"Decided by {d.decided_by}.")
    elif d.unavoidable:
        bits.append("No change to today's plan could fix this; it needs a different vehicle or a smaller order.")
    else:
        bits.append("Orders were served by priority; this one ranked below the orders that took the remaining capacity.")
    if d.override_note:
        bits.append(f"Dispatcher note: {d.override_note}.")
    if o.deferred_yesterday:
        bits.append("It was already deferred yesterday, so it should be first in line on the next run.")
    elif o.days_since_last_served and o.days_since_last_served > 2:
        bits.append(f"Its outlet has gone {o.days_since_last_served} days without a delivery.")
    return " ".join(bits)


def deferral_view(d: m.Deferral) -> dict:
    o = d.order
    return dict(id=d.id, order_ref=o.order_ref, order_id=o.id, outlet_id=o.outlet_id, brand=o.brand,
                district=o.district, temp=o.temp_requirement, volume_m3=o.order_volume_m3,
                status="DEFERRED", reason_code=d.reason_code, reason_text=d.reason_text,
                constraint=CONSTRAINT_OF.get(d.reason_code, d.reason_code), explanation=explanation(d),
                unavoidable=d.unavoidable, decided_by=d.decided_by, override_note=d.override_note,
                rescheduled_for=d.rescheduled_for, deferred_yesterday=o.deferred_yesterday,
                days_since_last_served=o.days_since_last_served)


def plan_view(db, plan):
    trips = db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id).order_by(m.Trip.vehicle_id, m.Trip.trip_no)).all()
    defs = db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id).order_by(m.Deferral.id)).all()
    return dict(plan_id=plan.id, date=plan.plan_date, status=plan.status, summary=json.loads(plan.summary or "{}"),
                trips=[trip_view(t) for t in trips], deferrals=[deferral_view(d) for d in defs])


def refresh_summary(db, plan):
    trips = db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id)).all()
    served = sum(len([s for s in t.stops if s.status != "cancelled"]) for t in trips)
    defs = db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id)).all()
    plan.summary = json.dumps(dict(total=served + len(defs), served=served, deferred=len(defs),
                                   unavoidable=sum(1 for d in defs if d.unavoidable),
                                   by_choice=sum(1 for d in defs if not d.unavoidable),
                                   trips=len(trips), vehicles_used=len({t.vehicle_id for t in trips})))


def capacity(db, date, depot):
    vs = db.scalars(select(m.Vehicle).where(m.Vehicle.depot == depot)).all()
    avail = [v for v in vs if v.status == "available"]
    orders = day_orders(db, date, depot)
    return dict(
        vehicles_total=len(vs), available=len(avail), in_workshop=len(vs) - len(avail),
        reefers_available=sum(v.temp == "reefer" for v in avail), vans_available=sum(v.type == "van" for v in avail),
        volume_capacity_m3=round(sum(v.volume_cap_m3 for v in avail), 1),
        reefer_volume_capacity_m3=round(sum(v.volume_cap_m3 for v in avail if v.temp == "reefer"), 1),
        demand_orders=len(orders), demand_volume_m3=round(sum(o.order_volume_m3 for o in orders), 1),
        chilled_demand_m3=round(sum(o.order_volume_m3 for o in orders if o.temp_requirement == "chilled"), 1))


# ---------------- endpoints ----------------
@router.get("/day")
def day(date: str = DEMO_DATE, user=Depends(dep), db: Session = Depends(get_db)):
    cal = db.get(m.CalendarDay, date)
    orders = day_orders(db, date, user.depot)
    plan = db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == user.depot).order_by(m.Plan.id.desc()))
    return dict(
        date=date, depot=user.depot,
        calendar=dict(festival=cal.festival if cal else None, festival_ramp=cal.festival_ramp if cal else 0,
                      payday=bool(cal.is_payday) if cal else False, monsoon=bool(cal.monsoon) if cal else False),
        capacity=capacity(db, date, user.depot),
        orders=[dict(id=o.id, order_ref=o.order_ref, outlet_id=o.outlet_id, brand=o.brand, district=o.district,
                     temp=o.temp_requirement, units=o.order_units, volume_m3=o.order_volume_m3,
                     weight_kg=o.order_weight_kg, status=o.status, dock_type=o.outlet.dock_type,
                     parking=o.outlet.parking_constraint, window=f"{o.outlet.window_open_time}-{o.outlet.window_close_time}",
                     mall_window=o.outlet.mall_window, deferred_yesterday=o.deferred_yesterday,
                     days_since_last_served=o.days_since_last_served) for o in orders],
        plan=plan_view(db, plan) if plan else None)


class RunBody(BaseModel):
    date: str = DEMO_DATE


@router.post("/plan/run")
def run_plan(body: RunBody, user=Depends(dep), db: Session = Depends(get_db)):
    existing = db.scalar(select(m.Plan).where(m.Plan.plan_date == body.date, m.Plan.depot == user.depot)
                         .order_by(m.Plan.id.desc()))
    if existing and existing.status == "published":
        raise HTTPException(409, "A plan for this day is already published.")
    orders = [o for o in day_orders(db, body.date, user.depot)]
    if not orders:
        raise HTTPException(404, "No confirmed orders for this day.")
    plan = existing or m.Plan(plan_date=body.date, depot=user.depot, created_by=user.id)
    if not existing:
        db.add(plan)
        db.flush()
    clear_trips(db, plan)
    for d in db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id)).all():
        db.delete(d)
    db.flush()
    ctx = build_ctx(db, body.date)
    result = allocate([order_dict(o) for o in orders], vehicles_for(db, user.depot), ctx)
    by_ref = {o.order_ref: o for o in orders}
    for o in orders:
        o.status = "confirmed"
    write_trips(db, plan, result["trips"], by_ref)
    for d in result["deferred"]:
        o = by_ref[d["order_ref"]]
        o.status = "deferred"
        db.add(m.Deferral(plan_id=plan.id, order_id=o.id, reason_code=d["reason_code"],
                          reason_text=d["reason_text"], unavoidable=d["unavoidable"], decided_by="engine"))
    db.flush()
    refresh_summary(db, plan)
    db.commit()
    return plan_view(db, plan)


class AssignBody(BaseModel):
    order_ref: str
    vehicle_id: str
    trip_no: int


class DeferBody(BaseModel):
    order_ref: str | None = None
    reason: str


def _rewrite(db, plan, assignments, orders):
    ctx = build_ctx(db, plan.plan_date)
    vehicles = vehicles_for(db, plan.depot)
    errs = validate_plan(assignments, [order_dict(o) for o in orders], vehicles, ctx)
    if errs:
        raise HTTPException(422, detail=dict(errors=errs))
    clear_trips(db, plan)
    by_ref = {o.order_ref: o for o in orders}
    write_trips(db, plan, layout(assignments, [order_dict(o) for o in orders], vehicles, ctx), by_ref)
    return by_ref


@router.post("/plan/{plan_id}/assign")
def assign(plan_id: int, body: AssignBody, user=Depends(dep), db: Session = Depends(get_db)):
    plan = get_plan(db, plan_id, user.depot, must_be_draft=True)
    orders = day_orders(db, plan.plan_date, plan.depot)
    if body.order_ref not in {o.order_ref for o in orders}:
        raise HTTPException(404, "Order not in this plan day")
    asg = [a for a in current_assignments(db, plan) if a["order_ref"] != body.order_ref]
    asg.append(body.model_dump())
    by_ref = _rewrite(db, plan, asg, orders)
    for d in db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id, m.Deferral.order_id == by_ref[body.order_ref].id)):
        db.delete(d)
    db.flush()
    refresh_summary(db, plan)
    db.commit()
    return plan_view(db, plan)


class AutoAssignBody(BaseModel):
    order_ref: str


@router.post("/plan/{plan_id}/assign-best")
def assign_best(plan_id: int, body: AutoAssignBody, user=Depends(dep), db: Session = Depends(get_db)):
    """The planning screen's Assign button: place one waiting order on the first vehicle/trip where the whole plan
    still validates (trips already in the plan first, so stops can share a trip). Refused with the reasons if none fits."""
    plan = get_plan(db, plan_id, user.depot, must_be_draft=True)
    orders = day_orders(db, plan.plan_date, plan.depot)
    if body.order_ref not in {o.order_ref for o in orders}:
        raise HTTPException(404, "Order not in this plan day")
    base = [a for a in current_assignments(db, plan) if a["order_ref"] != body.order_ref]
    ctx, vehicles = build_ctx(db, plan.plan_date), vehicles_for(db, plan.depot)
    ods = [order_dict(o) for o in orders]
    taken = sorted({(a["vehicle_id"], a["trip_no"]) for a in base})
    cands = taken + [(v["vehicle_id"], n) for v in vehicles for n in (1, 2) if (v["vehicle_id"], n) not in taken]
    best = None
    for vid, n in cands:
        cand = dict(order_ref=body.order_ref, vehicle_id=vid, trip_no=n)
        errs = validate_plan(base + [cand], ods, vehicles, ctx)
        if not errs:
            return assign(plan_id, AssignBody(**cand), user, db)
        if best is None or len(errs) < len(best):
            best = errs
    raise HTTPException(422, detail=dict(errors=best or ["No available vehicle can take this order."]))


@router.post("/plan/{plan_id}/defer")
def defer(plan_id: int, body: DeferBody, user=Depends(dep), db: Session = Depends(get_db)):
    plan = get_plan(db, plan_id, user.depot, must_be_draft=True)
    if len((body.reason or "").strip()) < 3 or not body.order_ref:
        raise HTTPException(422, detail=dict(errors=["Give a reason for deferring this order."]))
    orders = day_orders(db, plan.plan_date, plan.depot)
    asg = [a for a in current_assignments(db, plan) if a["order_ref"] != body.order_ref]
    by_ref = _rewrite(db, plan, asg, orders)
    o = by_ref.get(body.order_ref)
    if not o:
        raise HTTPException(404, "Order not found")
    o.status = "deferred"
    existing = db.scalar(select(m.Deferral).where(m.Deferral.plan_id == plan.id, m.Deferral.order_id == o.id))
    if not existing:
        db.add(m.Deferral(plan_id=plan.id, order_id=o.id, reason_code="DISPATCHER_CHOICE",
                          reason_text=body.reason.strip(), unavoidable=False, decided_by=user.username))
    else:       # the dispatcher confirms (or overrides) the engine's deferral and records their own reason
        existing.decided_by, existing.override_note = user.username, body.reason.strip()
    db.flush()
    refresh_summary(db, plan)
    db.commit()
    return plan_view(db, plan)


@router.post("/plan/{plan_id}/publish")
def publish(plan_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    plan = get_plan(db, plan_id, user.depot, must_be_draft=True)
    resched = next_operating_date(db, plan.plan_date)
    trips = db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id)).all()
    if not trips:
        raise HTTPException(422, detail=dict(errors=["Nothing is planned yet."]))
    plan.status = "published"
    for d in db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id)).all():
        d.rescheduled_for = resched
        notify(db, "store", "deferral",
               f"Order {d.order.order_ref} could not be delivered on {plan.plan_date}. Reason: {d.reason_text} "
               f"New delivery date: {resched}.", outlet_id=d.order.outlet_id)
    for t in trips:
        notify(db, "loader", "plan", f"Loading plan published: {t.vehicle_id} trip {t.trip_no}, {t.brand} {t.district}, "
               f"{len(t.stops)} stops, depart {t.depart_time}.")
        notify(db, "driver", "plan", f"Route ready: trip {t.trip_no} to {t.district} ({len(t.stops)} stops), "
               f"depart {t.depart_time}.", vehicle_id=t.vehicle_id)
        for s in t.stops:
            notify(db, "store", "eta", f"Order {s.order.order_ref} is scheduled for {plan.plan_date}. Expected arrival "
                   f"{s.eta} (window {s.window}) on {t.vehicle_id}.", outlet_id=s.order.outlet_id)
    db.flush()
    refresh_summary(db, plan)
    db.commit()
    return plan_view(db, plan)


@router.post("/stops/{stop_id}/defer")
def defer_stop(stop_id: int, body: DeferBody, user=Depends(dep), db: Session = Depends(get_db)):
    """Mid-day change on a published plan (e.g. breakdown). Drivers who recorded the stop offline
    before this moment keep their record when they sync (see driver.sync)."""
    s = db.get(m.TripStop, stop_id)
    if not s or s.trip.depot != user.depot:
        raise HTTPException(404, "Stop not found")
    if s.status != "pending":
        raise HTTPException(409, "This stop already has an outcome.")
    if len((body.reason or "").strip()) < 3:
        raise HTTPException(422, detail=dict(errors=["Give a reason."]))
    plan = db.get(m.Plan, s.trip.plan_id)
    resched = next_operating_date(db, plan.plan_date)
    s.status = "cancelled"
    s.order.status = "deferred"
    db.add(m.Deferral(plan_id=plan.id, order_id=s.order_id, reason_code="DISPATCHER_CHOICE", reason_text=body.reason.strip(),
                      unavoidable=False, decided_by=user.username, rescheduled_for=resched))
    msg = f"Stop cancelled: {s.order.outlet_id} ({s.order.order_ref}). Reason: {body.reason.strip()}"
    notify(db, "driver", "change", msg, vehicle_id=s.trip.vehicle_id)
    notify(db, "loader", "change", msg)
    notify(db, "store", "deferral", f"Order {s.order.order_ref} was deferred. Reason: {body.reason.strip()} New delivery date: {resched}.",
           outlet_id=s.order.outlet_id)
    db.flush()
    refresh_summary(db, plan)
    db.commit()
    return dict(ok=True)


@router.get("/live")
def live(date: str = DEMO_DATE, user=Depends(dep), db: Session = Depends(get_db)):
    plan = db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == user.depot,
                                          m.Plan.status == "published").order_by(m.Plan.id.desc()))
    if not plan:
        return dict(published=False, trips=[], issues=[], alerts=[])
    drivers = {u.vehicle_id: u.display_name for u in db.scalars(select(m.User).where(m.User.role == "driver"))}
    trips, alerts = [], []
    for t in db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id).order_by(m.Trip.vehicle_id, m.Trip.trip_no)):
        v = trip_view(t)
        done = [s for s in v["stops"] if s["status"] in ("delivered", "partial", "failed")]
        v["done"], v["total"] = len(done), len([s for s in v["stops"] if s["status"] != "cancelled"])
        v["driver"] = drivers.get(t.vehicle_id)
        for s in v["stops"]:
            s["late"] = bool(s["time_in"] and s["time_in"] > s["window"][6:])
            if s["status"] == "failed":
                alerts.append(f"{t.vehicle_id}: delivery failed at {s['outlet_id']} - {s['note'] or 'no note'}")
            if s["late"]:
                alerts.append(f"{t.vehicle_id}: arrived late at {s['outlet_id']} ({s['time_in']}, window closes {s['window'][6:]})")
            if s["conflict_note"]:
                alerts.append(f"{t.vehicle_id}: sync conflict at {s['outlet_id']} - {s['conflict_note']}")
        trips.append(v)
    issues = [dict(id=i.id, trip_id=i.trip_id, order_ref=db.get(m.Order, i.order_id).order_ref, type=i.issue_type,
                   note=i.note, at=i.created_at.isoformat() + "Z", resolved=i.resolved)
              for i in db.scalars(select(m.LoadingIssue).join(m.Trip, m.Trip.id == m.LoadingIssue.trip_id)
                                  .where(m.Trip.plan_id == plan.id).order_by(m.LoadingIssue.id.desc()))]
    return dict(published=True, plan_id=plan.id, trips=trips, issues=issues, alerts=alerts)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(issue_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    i = db.get(m.LoadingIssue, issue_id)
    if not i:
        raise HTTPException(404, "Issue not found")
    i.resolved = True
    notify(db, "loader", "issue", f"Dispatcher resolved the loading issue on trip {i.trip_id}.")
    db.commit()
    return dict(ok=True)


@router.get("/deferrals")
def deferrals(date: str = DEMO_DATE, user=Depends(dep), db: Session = Depends(get_db)):
    plan_ids = [p.id for p in db.scalars(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == user.depot))]
    rows = db.scalars(select(m.Deferral).where(m.Deferral.plan_id.in_(plan_ids)).order_by(m.Deferral.id)).all() if plan_ids else []
    by_reason = {}
    for d in rows:
        by_reason[d.reason_code] = by_reason.get(d.reason_code, 0) + 1
    return dict(date=date, count=len(rows), by_reason=by_reason, repeat_skips=sum(1 for d in rows if d.order.deferred_yesterday),
                rows=[deferral_view(d) for d in rows])


class RescheduleBody(BaseModel):
    date: str
    note: str | None = None


@router.post("/deferrals/{deferral_id}/reschedule")
def reschedule(deferral_id: int, body: RescheduleBody, user=Depends(dep), db: Session = Depends(get_db)):
    d = db.get(m.Deferral, deferral_id)
    if not d:
        raise HTTPException(404, "Deferral not found")
    d.rescheduled_for, d.override_note = body.date, body.note
    notify(db, "store", "deferral", f"Order {d.order.order_ref} is now rescheduled for {body.date}.", outlet_id=d.order.outlet_id)
    db.commit()
    return deferral_view(d)
