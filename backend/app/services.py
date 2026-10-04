import json
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from . import models as m

LK = timezone(timedelta(hours=5, minutes=30))


def now_lk() -> datetime:
    return datetime.now(LK)


def parse_ts(s: str | None) -> datetime:
    """ISO timestamp from a device -> naive UTC (the DB convention)."""
    if not s:
        return datetime.utcnow()
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d.astimezone(timezone.utc).replace(tzinfo=None) if d.tzinfo else d


def is_operating(db: Session, d: str) -> bool:
    row = db.get(m.CalendarDay, d)
    return bool(row.is_operating) if row else date.fromisoformat(d).weekday() != 6   # Mon-Sat


def next_operating_date(db: Session, d: str) -> str:
    cur = date.fromisoformat(d)
    for _ in range(14):
        cur += timedelta(days=1)
        if is_operating(db, cur.isoformat()):
            break
    return cur.isoformat()


def build_ctx(db: Session, plan_date: str):
    from .engine import Context
    travel = {r.district: dict(depot_to_district_km=r.depot_to_district_km,
                               depot_to_district_freeflow_min=r.depot_to_district_freeflow_min,
                               inter_stop_km=r.inter_stop_km, inter_stop_freeflow_min=r.inter_stop_freeflow_min)
              for r in db.scalars(select(m.DistrictTravel))}
    allowance = {(r.brand, r.dock_type): r.service_allowance_min for r in db.scalars(select(m.ServiceAllowance))}
    fuel = {}
    day = db.get(m.CalendarDay, plan_date)
    if day:
        week = [c.date for c in db.scalars(select(m.CalendarDay).where(
            m.CalendarDay.iso_year == day.iso_year, m.CalendarDay.iso_week == day.iso_week))]
        q = (select(m.Trip.vehicle_id, func.sum(m.Trip.fuel_l)).join(m.Plan, m.Plan.id == m.Trip.plan_id)
             .where(m.Plan.status == "published", m.Plan.plan_date.in_(week), m.Plan.plan_date != plan_date)
             .group_by(m.Trip.vehicle_id))
        fuel = {vid: float(total or 0) for vid, total in db.execute(q)}
    return Context(travel=travel, allowance=allowance, fuel_used_week=fuel)


def vehicles_for(db: Session, depot: str) -> list[dict]:
    return [dict(vehicle_id=v.vehicle_id, type=v.type, temp=v.temp, weight_cap_kg=v.weight_cap_kg,
                 volume_cap_m3=v.volume_cap_m3, km_per_l=v.km_per_l, weekly_fuel_quota_l=v.weekly_fuel_quota_l,
                 depot=v.depot)
            for v in db.scalars(select(m.Vehicle).where(m.Vehicle.depot == depot, m.Vehicle.status == "available"))]


def order_dict(o: m.Order) -> dict:
    ol = o.outlet
    return dict(order_ref=o.order_ref, outlet_id=o.outlet_id, brand=o.brand, district=o.district, depot=o.depot,
                dock_type=ol.dock_type, parking_constraint=ol.parking_constraint, mall_window=ol.mall_window,
                window_open_time=ol.window_open_time, window_close_time=ol.window_close_time,
                temp_requirement=o.temp_requirement, order_units=o.order_units, order_weight_kg=o.order_weight_kg,
                order_volume_m3=o.order_volume_m3, deferred_yesterday=o.deferred_yesterday,
                days_since_last_served=o.days_since_last_served)


def notify(db: Session, role: str, kind: str, message: str, outlet_id=None, vehicle_id=None):
    db.add(m.Notification(role=role, kind=kind, message=message, outlet_id=outlet_id, vehicle_id=vehicle_id))


def stop_view(s: m.TripStop) -> dict:
    o, ol = s.order, s.order.outlet
    return dict(stop_id=s.id, seq=s.seq, order_id=o.id, order_ref=o.order_ref, outlet_id=o.outlet_id,
                district=o.district, brand=o.brand, temp=o.temp_requirement, units=o.order_units,
                items=json.loads(o.items_json) if o.items_json else [], temp_req=o.temp_requirement,
                volume_m3=o.order_volume_m3, weight_kg=o.order_weight_kg, dock_type=ol.dock_type,
                parking=ol.parking_constraint, mall_window=ol.mall_window, eta=s.eta, window=s.window,
                status=s.status, time_in=s.time_in, time_out=s.time_out, note=s.note,
                conflict_note=s.conflict_note, has_photo=bool(s.pod_photo), loaded=bool(s.loaded))


def trip_view(t: m.Trip) -> dict:
    from sqlalchemy.orm import object_session
    v = object_session(t).get(m.Vehicle, t.vehicle_id)
    return dict(vehicle_type=v.type if v else None, vehicle_temp=v.temp if v else None,
                volume_cap_m3=v.volume_cap_m3 if v else None, weight_cap_kg=v.weight_cap_kg if v else None,
                budget_min=270 if t.brand == "Fresh" else 480, trip_id=t.id, vehicle_id=t.vehicle_id, trip_no=t.trip_no, brand=t.brand, district=t.district,
                depot=t.depot, depart_time=t.depart_time, minutes=t.minutes, fuel_l=t.fuel_l,
                volume_m3=t.volume_m3, weight_kg=t.weight_kg, status=t.status,
                stops=[stop_view(s) for s in t.stops])
