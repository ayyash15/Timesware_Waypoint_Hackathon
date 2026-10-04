"""Frontend-contract adapter.

The locked Designathon prototype reads ONE global object, `WP_DATA`, from /js/data.js.
This module builds that object from the real database in exactly the shape (field names,
string formats, status vocabulary) the prototype's pages already expect, so the static
files can be served unmodified while the numbers come from the live backend.

Backend model -> service -> THIS ADAPTER -> existing frontend contract.
Extra fields (reasonCode, explanation, ...) are additive; the prototype ignores them.
"""
import json
import math
from datetime import date as _date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models as m
from .services import next_operating_date

REASON_LABEL = {
    "REEFER_CAPACITY": "Refrigerated capacity",
    "NO_COMPATIBLE_VEHICLE": "Vehicle access",
    "ORDER_EXCEEDS_VEHICLE_CAPACITY": "Order too large",
    "FLEET_CAPACITY": "Fleet capacity",
    "TRIP_TIME_BUDGET": "Trip time budget",
    "DELIVERY_WINDOW": "Delivery window",
    "FUEL_QUOTA": "Fuel quota",
    "DISPATCHER_CHOICE": "Dispatcher decision",
}
DASH = "\u2013"
DOT = "\u00b7"


def _d(s: str) -> _date:
    return _date.fromisoformat(s)


def _long(d: _date) -> str:
    return d.strftime("%a, %d %b %Y")


def _short(d: _date) -> str:
    return f"{d.strftime('%a')}, {d.day} {d.strftime('%b')}"


def _m3(v: float) -> str:
    return f"{v:.1f} m\u00b3"


def _kg(v: float) -> str:
    return f"{v:.0f} kg"


def _window(open_t: str, close_t: str, mall: str | None) -> str:
    if mall and "-" in mall:
        return mall.replace("-", DASH) + " (mall)"
    return f"{open_t}{DASH}{close_t}"


def _access(outlet: m.Outlet) -> str:
    if outlet.parking_constraint == "van_only":
        return "Van only"
    if outlet.mall_window:
        return "Mall bay"
    txt = (outlet.dock_type or "").replace("_", " ").strip()
    return txt[:1].upper() + txt[1:] if txt else "Street"


def _published_plan(db: Session, date: str, depot: str):
    return db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == depot,
                                          m.Plan.status == "published").order_by(m.Plan.id.desc()))


def _latest_plan(db: Session, date: str, depot: str):
    return db.scalar(select(m.Plan).where(m.Plan.plan_date == date, m.Plan.depot == depot).order_by(m.Plan.id.desc()))


def _trip_name(t: m.Trip) -> str:
    return f"{t.district} {t.brand} {DOT} Trip {t.trip_no}"


def build_wp_data(db: Session, date: str, depot: str = "Peliyagoda", vehicle_id: str | None = None,
                  trip_no: int | None = None) -> dict:
    d = _d(date)
    orders = db.scalars(select(m.Order).where(m.Order.delivery_date == date, m.Order.depot == depot)
                        .order_by(m.Order.id)).all()
    plan = _latest_plan(db, date, depot)
    pub = _published_plan(db, date, depot)
    deferred_ids = set()
    deferrals = []
    if plan:
        deferrals = db.scalars(select(m.Deferral).where(m.Deferral.plan_id == plan.id).order_by(m.Deferral.id)).all()
        deferred_ids = {x.order_id for x in deferrals}
    trips = db.scalars(select(m.Trip).where(m.Trip.plan_id == plan.id)
                       .order_by(m.Trip.depart_time, m.Trip.vehicle_id, m.Trip.trip_no)).all() if plan else []

    # ---- orders -------------------------------------------------------------------
    def at_risk(o: m.Order) -> bool:
        return o.id in deferred_ids or o.status == "deferred" or (not plan and bool(o.deferred_yesterday))

    wp_orders = [dict(
        id=o.order_ref, outlet=o.outlet_id, brand=o.brand, district=o.district,
        temp="Chilled" if o.temp_requirement == "chilled" else "Ambient",
        volume=_m3(o.order_volume_m3), weight=_kg(o.order_weight_kg),
        window=_window(o.outlet.window_open_time, o.outlet.window_close_time, o.outlet.mall_window),
        access=_access(o.outlet), status="At risk" if at_risk(o) else "Confirmed") for o in orders]

    # ---- capacity -----------------------------------------------------------------
    vehicles = db.scalars(select(m.Vehicle).where(m.Vehicle.depot == depot)).all()
    avail = [v for v in vehicles if v.status == "available"]
    used_ids = {t.vehicle_id for t in trips}
    vmap = {v.vehicle_id: v for v in vehicles}
    capacity = dict(
        confirmedOrders=len(orders), availableVehicles=len(avail),
        reeferUsed=sum(1 for vid in used_ids if vmap[vid].temp == "reefer"),
        reeferTotal=sum(1 for v in avail if v.temp == "reefer"),
        vanUsed=sum(1 for vid in used_ids if vmap[vid].type == "van"),
        vanTotal=sum(1 for v in avail if v.type == "van"),
        atRisk=sum(1 for o in orders if at_risk(o)),
        # additive: tiles that were hardcoded in the HTML are filled from these by js/wp-live.js
        demandVolumeM3=round(sum(o.order_volume_m3 for o in orders), 1),
        demandWeightKg=round(sum(o.order_weight_kg for o in orders)),
        planStatus=plan.status if plan else None, planId=plan.id if plan else None,
        deferredCount=len(deferrals), workshop=len(vehicles) - len(avail))

    # ---- deferrals ----------------------------------------------------------------
    from .dispatcher import explanation
    from .engine import CONSTRAINT_OF
    wp_def = []
    for x in deferrals:
        o = x.order
        wp_def.append(dict(
            outlet=o.outlet_id, brand=o.brand, district=o.district,
            reason=REASON_LABEL.get(x.reason_code, x.reason_code),
            deferredYesterday=bool(o.deferred_yesterday), daysSince=int(o.days_since_last_served or 0),
            nextRun=_short(_d(x.rescheduled_for or next_operating_date(db, date))),
            # additive, explainable-deferral fields (prototype ignores them)
            orderId=o.order_ref, status="DEFERRED", reasonCode=x.reason_code,
            constraint=CONSTRAINT_OF.get(x.reason_code, x.reason_code),
            explanation=explanation(x), unavoidable=bool(x.unavoidable), decidedBy=x.decided_by))

    # ---- trips / dock queue -------------------------------------------------------
    drivers = {u.vehicle_id: u.display_name for u in db.scalars(select(m.User).where(m.User.role == "driver")) if u.vehicle_id}
    open_issue_trips = set(db.scalars(select(m.LoadingIssue.trip_id).where(m.LoadingIssue.resolved == False)).all())  # noqa: E712
    wp_trips, dock = [], []
    for t in (trips if pub else []):
        live_stops = [s for s in t.stops if s.status != "cancelled"]
        done = [s for s in live_stops if s.status in ("delivered", "partial", "failed")]
        pending = [s for s in live_stops if s.status == "pending"]
        has_problem = t.id in open_issue_trips or any(s.status == "failed" or s.conflict_note for s in live_stops)
        if has_problem:
            status = "Issue Reported"
        elif t.status == "completed":
            status = "Completed"
        elif t.status == "departed":
            status = "In Transit"
        else:
            status = {"planned": "Queued", "loading": "Loading", "ready": "Ready"}.get(t.status, t.status.title())
        total = len(live_stops)
        if pending:
            nxt = pending[0]
            stop_txt = f"{len(done) + 1} of {total} {DOT} {nxt.order.outlet_id}"
            eta = nxt.eta
        else:
            stop_txt, eta = "Completed", "\u2014"
        wp_trips.append(dict(vehicle=t.vehicle_id, driver=drivers.get(t.vehicle_id, "Unassigned"),
                             trip=_trip_name(t), stop=stop_txt, progress=round(100 * len(done) / total) if total else 0,
                             eta=eta, status=status))
        dock.append(dict(vehicle=t.vehicle_id, tripId=t.id, tripNo=t.trip_no, departure=t.depart_time, trip=_trip_name(t),
                         brand=t.brand, district=t.district,
                         status="Loaded" if t.status in ("ready", "departed", "completed") else
                                "Loading" if t.status == "loading" else "Queued"))

    # ---- loader / driver single-trip views ---------------------------------------
    focus = None
    if pub and trips:
        pref = vehicle_id
        if not pref:
            drv = db.scalar(select(m.User).where(m.User.role == "driver"))
            pref = drv.vehicle_id if drv else None
        cands = [t for t in trips if t.vehicle_id == pref and (trip_no is None or t.trip_no == trip_no)]
        if not cands:
            cands = [t for t in trips if trip_no is None or t.trip_no == trip_no] or list(trips)
        focus = cands[0]
    loading_stops, driver_stops = [], []
    focus_info = None
    if focus:
        focus_info = dict(vehicle=focus.vehicle_id, tripId=focus.id, tripNo=focus.trip_no, trip=_trip_name(focus),
                          departure=focus.depart_time, status=focus.status,
                          driver=drivers.get(focus.vehicle_id, "Unassigned"))
        live_stops = [s for s in focus.stops if s.status != "cancelled"]
        for s in reversed(live_stops):                       # last stop is loaded first
            o = s.order
            loading_stops.append(dict(seq=s.seq + 1, loaded=bool(s.loaded), stopId=s.id, orderId=o.id, tripId=focus.id, outlet=o.outlet_id, order=o.order_ref, items=f"{o.order_units} units",
                                      temp="Chilled" if o.temp_requirement == "chilled" else "Ambient",
                                      volume=_m3(o.order_volume_m3), access=_access(o.outlet)))
        current_marked = False
        for s in live_stops:
            if s.status in ("delivered", "partial", "failed"):
                st = "Done"
            elif not current_marked:
                st, current_marked = "Current", True
            else:
                st = "Upcoming"
            open_t, close_t = s.window.split("-")
            driver_stops.append(dict(seq=s.seq + 1, stopId=s.id, tripId=focus.id, outlet=s.order.outlet_id, eta=s.eta,
                                     window=f"{open_t}{DASH}{close_t}", status=st))

    # ---- capacity planning (derived from the day's confirmed demand, not a forecast) -----
    monday = d - timedelta(days=d.weekday())
    cal = db.get(m.CalendarDay, date)
    label = f"Week of {monday.day} {monday.strftime('%b')}" + (f" {DASH} Festival ramp" if cal and cal.festival_ramp else "")
    avg_cap = (sum(v.volume_cap_m3 for v in avail) / len(avail)) if avail else 1
    reefers = [v for v in avail if v.temp == "reefer"]
    avg_reefer = (sum(v.volume_cap_m3 for v in reefers) / len(reefers)) if reefers else 1
    plan_rows = []
    for brand in ("Fresh", "Style", "Tech"):
        bo = [o for o in orders if o.brand == brand]
        if not bo:
            continue
        vol = sum(o.order_volume_m3 for o in bo)
        chilled = sum(o.order_volume_m3 for o in bo if o.temp_requirement == "chilled")
        plan_rows.append(dict(week=label, brand=brand, depot=depot, forecast=f"{vol:.0f} m\u00b3",
                              chilled=f"{chilled:.0f} m\u00b3", vehiclesNeeded=math.ceil(vol / avg_cap),
                              reeferNeeded=math.ceil(chilled / avg_reefer) if chilled else 0))

    return dict(today=_long(d), depot=depot, capacity=capacity, orders=wp_orders, deferrals=wp_def,
                trips=wp_trips, dockQueue=dock, loadingStops=loading_stops, driverStops=driver_stops, focus=focus_info,
                capacityPlanning=plan_rows,
                meta=dict(source="backend", date=date, planStatus=plan.status if plan else None))


def render_data_js(data: dict) -> str:
    return ("/* Generated by the Waypoint backend from the live database. Same shape as the original prototype data. */\n"
            "const WP_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")
