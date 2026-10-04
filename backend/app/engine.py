"""Allocation engine for Waypoint Group.

Pure Python (no DB). Takes plain dicts, returns a plan plus a deferral record for
every order that could not be served. The same function powers:
  * auto-allocation in the dispatcher screen
  * manual / assisted planning (validate_plan re-checks any hand-edited plan)
  * the Datathon Task 2B file (same column names as task2b_peak_day_scenarios.csv)
"""
from __future__ import annotations
from dataclasses import dataclass, field

FRESH_BUDGET_MIN = 270      # Fresh trips, 3:30 AM - 8:00 AM
OTHER_BUDGET_MIN = 480      # Style + Tech trips combined, trading day
MAX_TRIPS = 2
FRESH_START = 3 * 60 + 30
OTHER_START = 7 * 60        # assumption: Style/Tech loading starts 07:00
FRESH_CLOSE = 8 * 60        # Fresh must arrive before stores open

UNAVOIDABLE = {"NO_COMPATIBLE_VEHICLE", "ORDER_EXCEEDS_VEHICLE_CAPACITY"}

REASON_TEXT = {
    "NO_COMPATIBLE_VEHICLE": "No available vehicle can serve this order (temperature or van-only access).",
    "ORDER_EXCEEDS_VEHICLE_CAPACITY": "Order is larger than any compatible vehicle can carry in one trip.",
    "REEFER_CAPACITY": "All refrigerated capacity at this depot was used by higher-priority orders.",
    "FLEET_CAPACITY": "All compatible vehicles were full for this district and brand.",
    "TRIP_TIME_BUDGET": "Adding this order would exceed the vehicle's daily trip-time budget.",
    "DELIVERY_WINDOW": "The order cannot reach the outlet inside its delivery or mall window.",
    "FUEL_QUOTA": "Compatible vehicles do not have enough weekly fuel quota left.",
}

# Constraint named for the dispatcher (used by the structured deferral payload)
CONSTRAINT_OF = {
    "NO_COMPATIBLE_VEHICLE": "temperature / outlet access",
    "ORDER_EXCEEDS_VEHICLE_CAPACITY": "weight / volume capacity",
    "REEFER_CAPACITY": "reefer capacity",
    "FLEET_CAPACITY": "fleet capacity",
    "TRIP_TIME_BUDGET": "trip-time budget",
    "DELIVERY_WINDOW": "delivery window",
    "FUEL_QUOTA": "weekly fuel quota",
    "DISPATCHER_CHOICE": "dispatcher decision",
}


def hm(s) -> int:
    h, m = str(s).strip().split(":")[:2]
    return int(h) * 60 + int(m)


def fmt(m: float) -> str:
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def cls_of(brand: str) -> str:
    return "fresh" if brand == "Fresh" else "other"


@dataclass
class Context:
    travel: dict                 # district -> row of district_travel.csv
    allowance: dict              # (brand, dock_type) -> minutes
    fuel_used_week: dict = field(default_factory=dict)   # vehicle_id -> litres already used this week


@dataclass
class Trip:
    vehicle: dict
    brand: str
    district: str
    stops: list = field(default_factory=list)
    trip_no: int = 0

    @property
    def cls(self):
        return cls_of(self.brand)


def prep(order: dict) -> dict:
    """Attach the effective delivery window (outlet window ∩ mall window ∩ Fresh 08:00 cut-off)."""
    o = dict(order)
    op, cl = hm(o["window_open_time"]), hm(o["window_close_time"])
    mw = o.get("mall_window")
    if mw and isinstance(mw, str) and "-" in mw:
        a, b = mw.split("-")
        op, cl = max(op, hm(a)), min(cl, hm(b))
    if o["brand"] == "Fresh":
        cl = min(cl, FRESH_CLOSE)
    o["_open"], o["_close"] = op, cl
    return o


def trip_metrics(trip: Trip, stops: list, start: int, ctx: Context) -> dict:
    tr = ctx.travel[trip.district]
    d2d, inter = tr["depot_to_district_freeflow_min"], tr["inter_stop_freeflow_min"]
    allow = [ctx.allowance[(trip.brand, s["dock_type"])] for s in stops]
    n = len(stops)
    minutes = d2d + inter * (n - 1) + sum(allow)
    km = 2 * tr["depot_to_district_km"] + tr["inter_stop_km"] * (n - 1)
    fuel = km / trip.vehicle["km_per_l"]
    depart = max(start, stops[0]["_open"] - d2d)
    t, ok, etas = depart + d2d, True, []
    for i, s in enumerate(stops):
        if i:
            t += inter
        if t > s["_close"]:
            ok = False
        begin = max(t, s["_open"])
        etas.append((t, begin))
        t = begin + allow[i]
    return dict(minutes=minutes, fuel=fuel, depart=depart, etas=etas, end=t, windows_ok=ok, d2d=d2d)


def sorted_stops(stops):
    return sorted(stops, key=lambda s: (s["_close"], s["_open"], s["order_ref"]))


def evaluate_vehicle(trips: list, ctx: Context):
    """Check every trip of one vehicle together. Returns (reason_or_None, metrics_per_trip)."""
    if not trips:
        return None, []
    veh = trips[0].vehicle
    if len(trips) > MAX_TRIPS:
        return "FLEET_CAPACITY", []
    used = {"fresh": 0, "other": 0}
    clock, fuel, out = {}, ctx.fuel_used_week.get(veh["vehicle_id"], 0.0), []
    for tr in sorted(trips, key=lambda t: t.trip_no):
        stops = sorted_stops(tr.stops)
        start = clock.get(tr.cls, FRESH_START if tr.cls == "fresh" else OTHER_START)
        if sum(s["order_volume_m3"] for s in stops) > veh["volume_cap_m3"] + 1e-9 or \
           sum(s["order_weight_kg"] for s in stops) > veh["weight_cap_kg"] + 1e-9:
            return "CAPACITY", out
        m = trip_metrics(tr, stops, start, ctx)
        out.append((tr, stops, m))
        used[tr.cls] += m["minutes"]
        fuel += m["fuel"]
        clock[tr.cls] = m["end"] + m["d2d"]          # return leg before the next load
        if not m["windows_ok"]:
            return "DELIVERY_WINDOW", out
    if used["fresh"] > FRESH_BUDGET_MIN or used["other"] > OTHER_BUDGET_MIN:
        return "TRIP_TIME_BUDGET", out
    if fuel > veh["weekly_fuel_quota_l"] + 1e-9:
        return "FUEL_QUOTA", out
    return None, out


def compatible(order: dict, veh: dict) -> bool:
    if order["temp_requirement"] == "chilled" and veh["temp"] != "reefer":
        return False
    if order.get("parking_constraint") == "van_only" and veh["type"] != "van":
        return False
    return veh["depot"] == order["depot"]


def priority(o: dict) -> tuple:
    score = (100 * int(o.get("deferred_yesterday") or 0)
             + 3 * min(int(o.get("days_since_last_served") or 0), 30)
             + (10 if o["temp_requirement"] == "chilled" else 0)
             + (5 if o["brand"] == "Fresh" else 0))
    return (-score, -o["order_volume_m3"], o["order_ref"])


def allocate(orders: list, vehicles: list, ctx: Context) -> dict:
    """Greedy, priority-first allocation. Every order ends up served or deferred with a reason."""
    orders = [prep(o) for o in orders]
    vstate = {v["vehicle_id"]: [] for v in vehicles}
    vmap = {v["vehicle_id"]: v for v in vehicles}
    deferred = []

    def try_trip(trip, order, is_new):
        trip.stops.append(order)
        vtrips = vstate[trip.vehicle["vehicle_id"]]
        if is_new:
            trip.trip_no = len(vtrips) + 1
            vtrips.append(trip)
        reason, _ = evaluate_vehicle(vtrips, ctx)
        if reason:
            trip.stops.pop()
            if is_new:
                vtrips.pop()
        return reason

    for o in sorted(orders, key=priority):
        cands = [v for v in vehicles if compatible(o, v)]
        if not cands:
            deferred.append(_defer(o, "NO_COMPATIBLE_VEHICLE"))
            continue
        fits = [v for v in cands if o["order_volume_m3"] <= v["volume_cap_m3"] and o["order_weight_kg"] <= v["weight_cap_kg"]]
        if not fits:
            deferred.append(_defer(o, "ORDER_EXCEEDS_VEHICLE_CAPACITY"))
            continue

        reasons, placed = [], False
        # 1) join an existing trip for the same brand + district (best fit first)
        joinable = [t for v in fits for t in vstate[v["vehicle_id"]] if t.brand == o["brand"] and t.district == o["district"]]
        joinable.sort(key=lambda t: t.vehicle["volume_cap_m3"] - sum(s["order_volume_m3"] for s in t.stops))
        for t in joinable:
            r = try_trip(t, o, False)
            if r is None:
                placed = True
                break
            reasons.append(r)
        # 2) open a new trip on the cheapest suitable vehicle
        if not placed:
            def cost(v):
                return (v["temp"] == "reefer" and o["temp_requirement"] != "chilled",
                        v["type"] == "van" and o.get("parking_constraint") != "van_only",
                        v["volume_cap_m3"])
            for v in sorted(fits, key=cost):
                if len(vstate[v["vehicle_id"]]) >= MAX_TRIPS:
                    reasons.append("FLEET_CAPACITY")
                    continue
                r = try_trip(Trip(v, o["brand"], o["district"]), o, True)
                if r is None:
                    placed = True
                    break
                reasons.append(r)
        if not placed:
            deferred.append(_defer(o, _summarise(reasons, o)))

    trips = _emit(vstate, vmap, ctx)
    served = sum(len(t["stops"]) for t in trips)
    return dict(trips=trips, deferred=deferred,
                summary=dict(total=len(orders), served=served, deferred=len(deferred),
                             unavoidable=sum(1 for d in deferred if d["unavoidable"])))


def _emit(vstate: dict, vmap: dict, ctx: Context) -> list:
    trips = []
    for vid, vt in vstate.items():
        _, ev = evaluate_vehicle(vt, ctx)
        for tr, stops, m in ev:
            trips.append(dict(
                vehicle_id=vid, trip_no=tr.trip_no, brand=tr.brand, district=tr.district,
                depot=vmap[vid]["depot"], minutes=round(m["minutes"], 1), fuel_l=round(m["fuel"], 2),
                depart=fmt(m["depart"]), volume_m3=round(sum(s["order_volume_m3"] for s in stops), 2),
                weight_kg=round(sum(s["order_weight_kg"] for s in stops), 1),
                stops=[dict(order_ref=s["order_ref"], outlet_id=s["outlet_id"], seq=i,
                            eta=fmt(m["etas"][i][0]), window=f'{fmt(s["_open"])}-{fmt(s["_close"])}')
                       for i, s in enumerate(stops)]))
    return trips


def layout(assignments: list, orders: list, vehicles: list, ctx: Context) -> list:
    """Turn [{order_ref, vehicle_id, trip_no}] into full trips (sequence, ETAs, minutes, fuel).
    Used after the dispatcher edits a plan by hand. Call validate_plan first."""
    omap = {o["order_ref"]: prep(o) for o in orders}
    vmap = {v["vehicle_id"]: v for v in vehicles}
    groups = {}
    for a in assignments:
        groups.setdefault((a["vehicle_id"], int(a["trip_no"])), []).append(omap[a["order_ref"]])
    vstate = {}
    for (vid, tn), stops in groups.items():
        vstate.setdefault(vid, []).append(Trip(vmap[vid], stops[0]["brand"], stops[0]["district"], stops, tn))
    return _emit(vstate, vmap, ctx)


def _summarise(reasons: list, o: dict) -> str:
    if not reasons:
        return "FLEET_CAPACITY"
    for code in ("DELIVERY_WINDOW", "FUEL_QUOTA", "TRIP_TIME_BUDGET"):
        if code in reasons and len(set(reasons)) == 1:
            return code
    if o["temp_requirement"] == "chilled":
        return "REEFER_CAPACITY"
    order = ["TRIP_TIME_BUDGET", "DELIVERY_WINDOW", "FUEL_QUOTA", "CAPACITY", "FLEET_CAPACITY"]
    top = max(set(reasons), key=lambda r: (reasons.count(r), -order.index(r)))
    return "FLEET_CAPACITY" if top == "CAPACITY" else top


def _defer(o: dict, code: str) -> dict:
    return dict(order_ref=o["order_ref"], outlet_id=o["outlet_id"], reason_code=code,
                reason_text=REASON_TEXT[code], unavoidable=code in UNAVOIDABLE,
                deferred_yesterday=int(o.get("deferred_yesterday") or 0),
                days_since_last_served=int(o.get("days_since_last_served") or 0))


def validate_plan(assignments: list, orders: list, vehicles: list, ctx: Context) -> list:
    """Re-check a (possibly hand-edited) plan. assignments: [{order_ref, vehicle_id, trip_no}].
    Returns a list of human-readable violations (empty list = feasible)."""
    omap = {o["order_ref"]: prep(o) for o in orders}
    vmap = {v["vehicle_id"]: v for v in vehicles}
    errs, seen, groups = [], set(), {}
    for a in assignments:
        ref, vid, tn = a["order_ref"], a["vehicle_id"], int(a["trip_no"])
        if ref in seen:
            errs.append(f"{ref}: assigned more than once (orders cannot be split)")
        seen.add(ref)
        if ref not in omap or vid not in vmap:
            errs.append(f"{ref}: unknown order or vehicle {vid}")
            continue
        if tn not in (1, 2):
            errs.append(f"{ref}: trip must be 1 or 2")
        if not compatible(omap[ref], vmap[vid]):
            errs.append(f"{ref}: {vid} cannot serve it (temperature, van-only access or depot)")
        groups.setdefault((vid, tn), []).append(omap[ref])
    byv = {}
    for (vid, tn), stops in groups.items():
        if len({(s["brand"], s["district"]) for s in stops}) > 1:
            errs.append(f"{vid} trip {tn}: mixes brands or districts")
        byv.setdefault(vid, []).append(Trip(vmap[vid], stops[0]["brand"], stops[0]["district"], stops, tn))
    for vid, trips in byv.items():
        r, _ = evaluate_vehicle(trips, ctx)
        if r:
            errs.append(f"{vid}: {REASON_TEXT.get(r, r)}")
    return errs
