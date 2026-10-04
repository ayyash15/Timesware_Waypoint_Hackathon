"""Seeds reference data from the shared CSVs plus one realistic delivery day.

Expected files in DATA_DIR: outlets.csv, vehicles.csv, calendar.csv,
district_travel.csv, service_allowance.csv  (the competition General Data folder).
"""
import csv, os, random
from sqlalchemy import select, func
from .config import DATA_DIR, DEMO_DATE, DEMAND_SCALE, SEED_PASSWORD
from .db import Base, engine, SessionLocal
from . import models as m
from .security import hash_password

WORKSHOP_COUNT = int(os.getenv("WORKSHOP_COUNT", "4"))


def read(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):          # competition CSVs are confidential and not in git: use the synthetic sample set
        path = os.path.join(os.path.dirname(__file__), "sample_data", name)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = []
        for r in csv.DictReader(f):
            rows.append({k.strip(): (v.strip() if isinstance(v, str) and v.strip() != "" else None) for k, v in r.items()})
        return rows


def f(x, default=0.0):
    return float(x) if x not in (None, "") else default


def seed_reference(db):
    for r in read("outlets.csv"):
        db.add(m.Outlet(outlet_id=r["outlet_id"], brand=r["brand"], district=r["district"], depot=r["depot"],
                        dock_type=r["dock_type"], parking_constraint=r["parking_constraint"],
                        mall_window=r.get("mall_window"), window_open_time=r["window_open_time"],
                        window_close_time=r["window_close_time"]))
    vrows = read("vehicles.csv")
    for r in vrows:
        db.add(m.Vehicle(vehicle_id=r["vehicle_id"], type=r["type"], temp=r["temp"],
                         weight_cap_kg=f(r["weight_cap_kg"]), volume_cap_m3=f(r["volume_cap_m3"]),
                         fuel_type=r.get("fuel_type") or "diesel", km_per_l=f(r["km_per_l"], 5),
                         weekly_fuel_quota_l=f(r["weekly_fuel_quota_l"], 500), depot=r["depot"]))
    for r in read("calendar.csv"):
        db.add(m.CalendarDay(date=r["date"], dow=int(f(r["dow"])), iso_year=int(f(r["iso_year"])),
                             iso_week=int(f(r["iso_week"])), is_payday=int(f(r["is_payday"])),
                             festival=r.get("festival"), festival_ramp=f(r.get("festival_ramp")),
                             monsoon=int(f(r.get("monsoon"))), is_operating=int(f(r.get("is_operating"), 1))))
    for r in read("district_travel.csv"):
        db.add(m.DistrictTravel(district=r["district"], depot=r["depot"],
                                depot_to_district_km=f(r["depot_to_district_km"]),
                                depot_to_district_freeflow_min=f(r["depot_to_district_freeflow_min"]),
                                inter_stop_km=f(r["inter_stop_km"]), inter_stop_freeflow_min=f(r["inter_stop_freeflow_min"])))
    for r in read("service_allowance.csv"):
        db.add(m.ServiceAllowance(brand=r["brand"], dock_type=r["dock_type"],
                                  service_allowance_min=f(r["service_allowance_min"])))
    db.flush()
    # a few vehicles are in the workshop on the demo day, as in the brief peak-day scenario
    ids = sorted(r["vehicle_id"] for r in vrows)
    for vid in ids[-WORKSHOP_COUNT:] if WORKSHOP_COUNT else []:
        db.get(m.Vehicle, vid).status = "in_workshop"


def seed_orders(db):
    rnd = random.Random(2026)
    s = DEMAND_SCALE
    n = 0
    for o in db.scalars(select(m.Outlet).order_by(m.Outlet.outlet_id)):
        specs = []
        if o.brand == "Fresh":
            specs.append(("ambient", rnd.uniform(2, 6), rnd.uniform(250, 900)))
            if rnd.random() < 0.65:
                specs.append(("chilled", rnd.uniform(1, 4), rnd.uniform(150, 600)))
        elif o.brand == "Style" and rnd.random() < 0.45:
            specs.append(("ambient", rnd.uniform(4, 10), rnd.uniform(100, 500)))
        elif o.brand == "Tech" and rnd.random() < 0.4:
            specs.append(("ambient", rnd.uniform(0.8, 3.5), rnd.uniform(250, 900)))
        skipped = o.brand == "Fresh" and rnd.random() < 0.12
        for temp, vol, wt in specs:
            n += 1
            vol, wt = round(vol * s, 1), round(wt * s, 0)
            db.add(m.Order(order_ref=f"WP{DEMO_DATE.replace("-", "")}-{n:03d}", outlet_id=o.outlet_id, brand=o.brand,
                           district=o.district, depot=o.depot, delivery_date=DEMO_DATE, temp_requirement=temp,
                           order_units=max(1, round(vol * 8)), order_weight_kg=wt, order_volume_m3=vol,
                           deferred_yesterday=int(skipped), days_since_last_served=rnd.randint(2, 5) if skipped else 1))
    return n


def seed_users(db):
    pw = hash_password(SEED_PASSWORD)
    veh = db.scalars(select(m.Vehicle).where(m.Vehicle.depot == "Peliyagoda", m.Vehicle.temp == "reefer",
                                             m.Vehicle.type == "truck", m.Vehicle.status == "available")
                     .order_by(m.Vehicle.vehicle_id)).first()
    outlet = db.scalars(select(m.Outlet).join(m.Order, m.Order.outlet_id == m.Outlet.outlet_id)
                        .where(m.Outlet.brand == "Fresh", m.Outlet.depot == "Peliyagoda")
                        .order_by(m.Outlet.outlet_id)).first()
    db.add_all([
        m.User(username="dispatcher", password_hash=pw, role="dispatcher", display_name="Nadeeka (Dispatcher)", depot="Peliyagoda"),
        m.User(username="loader", password_hash=pw, role="loader", display_name="Sampath (Loader)", depot="Peliyagoda"),
        m.User(username="driver", password_hash=pw, role="driver", display_name="Ruwan (Driver)", depot="Peliyagoda",
               vehicle_id=veh.vehicle_id if veh else None),
        m.User(username="store", password_hash=pw, role="store", display_name="Fathima (Store Manager)",
               depot="Peliyagoda", outlet_id=outlet.outlet_id if outlet else None),
    ])


def seed_if_empty():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(m.User)):
            return "already seeded"
        seed_reference(db)
        n = 0
        if os.getenv("SEED_BULK") == "1":
            n = seed_orders(db)
        db.flush()
        seed_users(db)
        db.commit()
        return f"seeded reference data, {n} orders for {DEMO_DATE}"


if __name__ == "__main__":
    print(seed_if_empty())
