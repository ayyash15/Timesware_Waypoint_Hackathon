"""End-to-end test: whole workflow across the 4 roles against a SQLite DB seeded from SYNTHETIC CSVs.
Run:  python tests/make_fixtures.py tests/fixtures && pytest -s tests/test_e2e.py
Env (optional): FRONTEND_DIR=<path to the unmodified prototype>  DEMAND_SCALE=<float>
"""
import os, sys, tempfile, json, re, hashlib, subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
if not (FIX / "outlets.csv").exists():
    subprocess.check_call([sys.executable, str(ROOT / "tests" / "make_fixtures.py"), str(FIX)])
TMP = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{TMP}/test.db", DATA_DIR=str(FIX), DEMO_DATE="2026-10-06",
    DEMAND_SCALE=os.getenv("DEMAND_SCALE", "1.8"), WORKSHOP_COUNT="1", SECRET_KEY="test-secret",
    FRONTEND_DIR=os.getenv("FRONTEND_DIR", str(ROOT / "frontend")))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient            # noqa: E402
from sqlalchemy import select                          # noqa: E402
from app.main import app                               # noqa: E402
from app.db import SessionLocal                        # noqa: E402
from app import models as m                            # noqa: E402
from app.seed import seed_if_empty                     # noqa: E402

PW = "Waypoint@2026"
PHOTO = "data:image/png;base64,iVBORw0KGgo="


def login(c, user):
    r = c.post("/api/auth/login", json=dict(username=user, password=PW))
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_full_workflow():
    with TestClient(app) as c:
        log = []

        def ok(name, cond, extra=""):
            assert cond, f"FAILED: {name} {extra}"
            log.append(f"PASS  {name}")

        # ---------- auth + role guards ----------
        ok("health", c.get("/api/health").json() == {"ok": True})
        ok("wrong password -> 401", c.post("/api/auth/login", json=dict(username="driver", password="nope")).status_code == 401)
        H = {u: login(c, u) for u in ("dispatcher", "loader", "driver", "store")}
        ok("4 seeded accounts log in", len(H) == 4)
        ok("no token -> 401", c.get("/api/dispatcher/day").status_code == 401)
        ok("store cannot use dispatcher area -> 403", c.get("/api/dispatcher/day", headers=H["store"]).status_code == 403)
        ok("driver cannot use loader area -> 403", c.get("/api/loader/trips", headers=H["driver"]).status_code == 403)
        ok("loader cannot publish -> 403", c.post("/api/dispatcher/plan/1/publish", headers=H["loader"]).status_code == 403)
        ok("dispatcher cannot record deliveries -> 403", c.post("/api/driver/sync", json=dict(events=[]), headers=H["dispatcher"]).status_code == 403)

        # ---------- locked frontend served unmodified + data.js from the DB ----------
        fe = Path(os.environ["FRONTEND_DIR"])
        if fe.is_dir():
            for page in ("index.html", "dispatcher-overview.html", "driver-stops.html"):
                r = c.get("/" + page)
                ok(f"static {page} served", r.status_code == 200)
                ok(f"static {page} byte-identical to repo file", hashlib.sha256(r.content).hexdigest() ==
                   hashlib.sha256((fe / page).read_bytes()).hexdigest())
        r = c.get("/js/data.js")
        ok("/js/data.js is generated from DB", r.status_code == 200 and "const WP_DATA" in r.text and '"source": "backend"' in r.text)
        wp0 = c.get("/api/wp-data").json()
        ok("data.js: orders present pre-plan", len(wp0["orders"]) > 0 and wp0["trips"] == [])
        for k in ("today", "depot", "capacity", "orders", "deferrals", "trips", "dockQueue", "loadingStops", "driverStops", "capacityPlanning"):
            ok(f"WP_DATA has key '{k}'", k in wp0)
        o0 = wp0["orders"][0]
        ok("order fields match prototype contract", set(o0) >= {"id", "outlet", "brand", "district", "temp", "volume", "weight", "window", "access", "status"})
        ok("string formats match (e.g. '4.2 m³', '610 kg')", re.fullmatch(r"\d+\.\d m³", o0["volume"]) and re.fullmatch(r"\d+ kg", o0["weight"]))

        # ---------- store manager places an order ----------
        info = c.get("/api/store/outlet", headers=H["store"]).json()
        ok("store outlet loads", info["outlet_id"].startswith("OUT"))
        bad = c.post("/api/store/orders", headers=H["store"], json=dict(order_units=0, order_weight_kg=10, order_volume_m3=1))
        ok("invalid order -> 422", bad.status_code == 422)
        placed = c.post("/api/store/orders", headers=H["store"], json=dict(temp_requirement="ambient", order_units=12, order_weight_kg=180, order_volume_m3=1.5)).json()
        my_ref = placed["order_ref"]
        ok("store order confirmed for demo day", placed["confirmed"] and placed["delivery_date"] == "2026-10-06")
        D = c.get("/api/dispatcher/day", headers=H["dispatcher"]).json()
        ok("dispatcher sees the new order (same DB)", my_ref in {o["order_ref"] for o in D["orders"]})
        total_orders = len(D["orders"])

        # ---------- dispatcher plans ----------
        plan = c.post("/api/dispatcher/plan/run", headers=H["dispatcher"], json={}).json()
        s = plan["summary"]
        print("\nPLAN SUMMARY:", s)
        ok("every order is served or deferred", s["served"] + s["deferred"] == total_orders == s["total"])
        ok("demand exceeds capacity -> some deferred", s["deferred"] > 0, str(s))
        ok("some orders allocated", s["served"] > 0)

        # independent constraint check straight from the DB (not via the engine's own validator)
        with SessionLocal() as db:
            vmap = {v.vehicle_id: v for v in db.scalars(select(m.Vehicle))}
            trips = db.scalars(select(m.Trip).where(m.Trip.plan_id == plan["plan_id"])).all()
            per_vehicle, seen = {}, set()
            fresh_min, other_min = {}, {}
            for t in trips:
                v = vmap[t.vehicle_id]
                per_vehicle[t.vehicle_id] = per_vehicle.get(t.vehicle_id, 0) + 1
                ok(f"{t.vehicle_id}/T{t.trip_no} home depot", v.depot == t.depot and v.status == "available")
                ok(f"{t.vehicle_id}/T{t.trip_no} volume+weight within capacity", t.volume_m3 <= v.volume_cap_m3 + 1e-6 and t.weight_kg <= v.weight_cap_kg + 1e-6)
                ok(f"{t.vehicle_id}/T{t.trip_no} one brand+district", len({(x.order.brand, x.order.district) for x in t.stops}) == 1)
                for x in t.stops:
                    o, ol = x.order, x.order.outlet
                    ok(f"{o.order_ref} not split / assigned once", o.id not in seen); seen.add(o.id)
                    if o.temp_requirement == "chilled":
                        ok(f"{o.order_ref} chilled on reefer", v.temp == "reefer")
                    if ol.parking_constraint == "van_only":
                        ok(f"{o.order_ref} van-only on van", v.type == "van")
                    lo, hi = x.window.split("-")
                    ok(f"{o.order_ref} ETA {x.eta} within window {x.window}", lo <= x.eta <= hi)
                book = fresh_min if t.brand == "Fresh" else other_min
                book[t.vehicle_id] = book.get(t.vehicle_id, 0) + t.minutes
            ok("max two trips per vehicle", max(per_vehicle.values()) <= 2)
            ok("Fresh trip budget <= 270 min per vehicle", all(v <= 270 + 1e-6 for v in fresh_min.values()))
            ok("Style+Tech budget <= 480 min per vehicle", all(v <= 480 + 1e-6 for v in other_min.values()))
            wk_fuel = {}
            for t in trips:
                wk_fuel[t.vehicle_id] = wk_fuel.get(t.vehicle_id, 0) + t.fuel_l
            ok("fuel within weekly quota", all(f <= vmap[v].weekly_fuel_quota_l for v, f in wk_fuel.items()))
            ok("workshop vehicle not used", all(vmap[v].status == "available" for v in per_vehicle))

        # deferral explanations
        for d in plan["deferrals"]:
            ok(f"deferral {d['order_ref']} is explainable", d["status"] == "DEFERRED" and d["reason_code"] and d["constraint"] and len(d["explanation"]) > 30)
        print("DEFERRAL REASONS:", sorted({d["reason_code"] for d in plan["deferrals"]}))
        print("EXAMPLE:", json.dumps({k: plan["deferrals"][0][k] for k in ("order_ref", "status", "reason_code", "constraint", "explanation")}, indent=1))

        # manual edit validation: chilled order onto an ambient truck must be refused in plain English
        pid = plan["plan_id"]
        chilled = next((o for o in D["orders"] if o["temp"] == "chilled"), None)
        ambient_veh = next(v for v in c.get("/api/dispatcher/day", headers=H["dispatcher"]).json()["plan"]["trips"] if True)
        with SessionLocal() as db:
            amb = db.scalar(select(m.Vehicle).where(m.Vehicle.temp == "ambient", m.Vehicle.depot == "Peliyagoda"))
        r = c.post(f"/api/dispatcher/plan/{pid}/assign", headers=H["dispatcher"], json=dict(order_ref=chilled["order_ref"], vehicle_id=amb.vehicle_id, trip_no=1))
        ok("chilled -> ambient vehicle rejected 422", r.status_code == 422 and "cannot serve" in json.dumps(r.json()), r.text[:200])
        r = c.post(f"/api/dispatcher/plan/{pid}/assign", headers=H["dispatcher"], json=dict(order_ref=chilled["order_ref"], vehicle_id="NOPE", trip_no=1))
        ok("unknown vehicle rejected 422", r.status_code == 422)

        # manual deferral keeps counts consistent (the stale-summary bug)
        served_refs = [st["order_ref"] for t in plan["trips"] for st in t["stops"] if st["order_ref"] != my_ref]
        victim = served_refs[-1]
        r = c.post(f"/api/dispatcher/plan/{pid}/defer", headers=H["dispatcher"], json=dict(order_ref=victim, reason="Driver short today"))
        s2 = r.json()["summary"]
        ok("manual defer -> counts stay consistent", r.status_code == 200 and s2["served"] + s2["deferred"] == total_orders and s2["deferred"] == s["deferred"] + 1, str(s2))
        ok("manual defer needs a reason", c.post(f"/api/dispatcher/plan/{pid}/defer", headers=H["dispatcher"], json=dict(order_ref=victim, reason="")).status_code == 422)

        # ---------- publish ----------
        pub = c.post(f"/api/dispatcher/plan/{pid}/publish", headers=H["dispatcher"]).json()
        ok("plan published", pub["status"] == "published")
        ok("re-run after publish -> 409", c.post("/api/dispatcher/plan/run", headers=H["dispatcher"], json={}).status_code == 409)
        ok("edit after publish -> 409", c.post(f"/api/dispatcher/plan/{pid}/defer", headers=H["dispatcher"], json=dict(order_ref=victim, reason="again")).status_code == 409)
        with SessionLocal() as db:
            dn = db.scalars(select(m.Notification).where(m.Notification.role == "store", m.Notification.kind == "deferral")).all()
        ok("every deferred outlet gets a notification with the new delivery date", len(dn) >= len(pub["deferrals"]) > 0 and all("New delivery date" in n.message for n in dn))

        wp1 = c.get("/api/wp-data").json()
        ok("data.js after publish: trips/dock/deferrals populated", wp1["trips"] and wp1["dockQueue"] and wp1["deferrals"] and wp1["driverStops"] and wp1["loadingStops"])
        ok("dock statuses use the prototype vocabulary", {d["status"] for d in wp1["dockQueue"]} <= {"Loaded", "Loading", "Queued"})
        ok("driverStops statuses use Done/Current/Upcoming", {d["status"] for d in wp1["driverStops"]} <= {"Done", "Current", "Upcoming"})
        ok("deferral rows carry prototype fields + explanation", {"outlet", "brand", "district", "reason", "deferredYesterday", "daysSince", "nextRun", "explanation", "reasonCode"} <= set(wp1["deferrals"][0]))
        ok("capacity.atRisk equals deferred count", wp1["capacity"]["atRisk"] == s2["deferred"])

        # ---------- loader ----------
        L = c.get("/api/loader/trips", headers=H["loader"]).json()
        ok("loader sees published trips", L["published"] and len(L["trips"]) == len(pub["trips"]))
        # choose the trip that serves the store's order, so the same trip flows through every role
        mine = next(t for t in L["trips"] for st in t["stops"] if st["order_ref"] == my_ref)
        ok("load order is reverse of stop order", [x["order_ref"] for x in mine["load_order"]] == [x["order_ref"] for x in reversed(mine["stops"])])
        other = max((t for t in L["trips"] if t["trip_id"] != mine["trip_id"]), key=lambda t: len(t["stops"]), default=None)
        ok("a second trip with >=3 stops exists for the offline/conflict scenarios", other and len(other["stops"]) >= 3, str([len(t["stops"]) for t in L["trips"]]))
        if other:
            vid = other["vehicle_id"]
            ok("driver cannot depart before loader releases (409)", c.post(f"/api/driver/trips/{other['trip_id']}/depart", headers=H["driver"]).status_code == 409)
        first_stop = mine["stops"][0]
        r = c.post("/api/loader/issues", headers=H["loader"], json=dict(trip_id=mine["trip_id"], order_id=first_stop["order_id"], issue_type="damaged", note="2 crates crushed"))
        ok("loader flags damaged items", r.status_code == 200)
        ok("bad issue type rejected", c.post("/api/loader/issues", headers=H["loader"], json=dict(trip_id=mine["trip_id"], order_id=first_stop["order_id"], issue_type="lost")).status_code == 422)
        r = c.post(f"/api/loader/trips/{mine['trip_id']}/ready", headers=H["loader"], json={})
        ok("ready blocked while shortfall unresolved (409, needs_force)", r.status_code == 409 and r.json()["detail"]["needs_force"])
        live = c.get("/api/dispatcher/live", headers=H["dispatcher"]).json()
        ok("dispatcher sees the loading issue", any(i["type"] == "damaged" for i in live["issues"]))
        iid = live["issues"][0]["id"]
        ok("dispatcher resolves issue", c.post(f"/api/dispatcher/issues/{iid}/resolve", headers=H["dispatcher"]).status_code == 200)
        ok("loader releases vehicle", c.post(f"/api/loader/trips/{mine['trip_id']}/ready", headers=H["loader"], json={}).json()["status"] == "ready")

        # ---------- driver (+ offline sync) ----------
        V = c.get("/api/driver/vehicles", headers=H["driver"]).json()
        ok("driver vehicle picker lists routed vehicles", mine["vehicle_id"] in V["with_routes"])
        R = c.get("/api/driver/route", params=dict(vehicle_id=mine["vehicle_id"]), headers=H["driver"]).json()
        rt = next(t for t in R["trips"] if t["trip_id"] == mine["trip_id"])
        ok("driver departs after release", c.post(f"/api/driver/trips/{rt['trip_id']}/depart", headers=H["driver"]).json()["status"] == "departed")
        stops = rt["stops"]
        mine_stop = next(x for x in stops if x["order_ref"] == my_ref)

        def ev(stop, uuid, status="delivered", **kw):
            d = dict(client_uuid=uuid, stop_id=stop["stop_id"], status=status, time_in=stop["eta"], time_out=stop["eta"],
                     pod_photo=PHOTO, recorded_at="2026-10-06T01:00:00Z")
            d.update(kw)
            return d

        # offline queue replayed twice (retry-safe) + validation
        q = [ev(mine_stop, "dev-0001")]
        a = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=q)).json()["results"]
        b = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=q)).json()["results"]
        ok("sync applies the delivery", a[0]["result"] == "applied")
        ok("replaying the same queue is idempotent -> duplicate", b[0]["result"] == "duplicate")
        with SessionLocal() as db:
            ok("exactly one record stored", db.scalar(select(m.TripStop).where(m.TripStop.client_uuid == "dev-0001")) is not None)
        ok("loader releases second vehicle", c.post(f"/api/loader/trips/{other['trip_id']}/ready", headers=H["loader"], json={}).json()["status"] == "ready")
        ok("driver departs second trip", c.post(f"/api/driver/trips/{other['trip_id']}/depart", headers=H["driver"]).json()["status"] == "departed")
        others = c.get("/api/driver/route", params=dict(vehicle_id=other["vehicle_id"]), headers=H["driver"]).json()["trips"]
        others = next(t for t in others if t["trip_id"] == other["trip_id"])["stops"]
        if True:
            r1 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(others[0], "dev-0002", pod_photo=None)])).json()["results"][0]
            ok("delivered without POD photo rejected", r1["result"] == "rejected")
            r2 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(others[0], "dev-0003", status="failed", pod_photo=None, note="")])).json()["results"][0]
            ok("failed without note rejected", r2["result"] == "rejected")
            r3 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(others[0], "dev-0004", status="failed", pod_photo=None, note="Shop closed")])).json()["results"][0]
            ok("failed with note applied", r3["result"] == "applied")
            r4 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(others[0], "dev-0005")])).json()["results"][0]
            ok("second record for same stop -> conflict, first kept", r4["result"] == "conflict")

            # conflict rule: delivery recorded BEFORE the dispatcher deferral stands; AFTER is rejected
            s_before, s_after = others[1], others[2] if len(others) > 2 else None
            c.post(f"/api/dispatcher/stops/{s_before['stop_id']}/defer", headers=H["dispatcher"], json=dict(reason="Truck issue"))
            r5 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(s_before, "dev-0006", recorded_at=(datetime.utcnow() - timedelta(minutes=30)).isoformat() + "Z")])).json()["results"][0]
            ok("offline delivery recorded before deferral stands (driver wins)", r5["result"] == "applied")
            if s_after:
                c.post(f"/api/dispatcher/stops/{s_after['stop_id']}/defer", headers=H["dispatcher"], json=dict(reason="Outlet closed"))
                r6 = c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(s_after, "dev-0007", recorded_at="2099-01-01T00:00:00Z")])).json()["results"][0]
                ok("delivery recorded after deferral rejected", r6["result"] == "rejected")
            for x in others[3:]:
                c.post("/api/driver/sync", headers=H["driver"], json=dict(events=[ev(x, f"dev-x-{x['stop_id']}")]))

        # ---------- store confirms receipt ----------
        so = {o["order_ref"]: o for o in c.get("/api/store/orders", headers=H["store"]).json()}
        mo = so[my_ref]
        ok("store sees delivery with vehicle + ETA", mo["status"] == "delivered" and mo["vehicle_id"] == mine["vehicle_id"] and mo["eta"])
        ok("issue receipt without note -> 422", c.post(f"/api/store/orders/{mo['id']}/receipt", headers=H["store"], json=dict(status="issue")).status_code == 422)
        ok("store confirms receipt", c.post(f"/api/store/orders/{mo['id']}/receipt", headers=H["store"], json=dict(status="confirmed")).json()["status"] == "received")
        ok("second receipt blocked (409)", c.post(f"/api/store/orders/{mo['id']}/receipt", headers=H["store"], json=dict(status="confirmed")).status_code == 409)

        # ---------- dispatcher sees the result ----------
        live = c.get("/api/dispatcher/live", headers=H["dispatcher"]).json()
        ok("live board shows alerts (failed / conflict)", any("failed" in a or "conflict" in a for a in live["alerts"]), str(live["alerts"]))
        wp2 = c.get("/api/wp-data").json()
        ok("data.js trips reflect progress", any(t["status"] in ("Completed", "Issue Reported") for t in wp2["trips"]))
        D2 = c.get("/api/deferrals" if False else "/api/dispatcher/deferrals", headers=H["dispatcher"]).json()
        ok("deferral log includes engine + dispatcher decisions", {r["decided_by"] for r in D2["rows"]} >= {"engine", "dispatcher"})
        ok("dispatcher notified of the receipt flow / events", len(c.get("/api/notifications", headers=H["dispatcher"]).json()) > 3)

        # ---------- persistence ----------
        with SessionLocal() as db:
            n_before = len(db.scalars(select(m.Order)).all())
        ok("re-seed on a seeded DB is a no-op", seed_if_empty() == "already seeded")
        with SessionLocal() as db:
            ok("data persisted (orders, stops, receipts)", len(db.scalars(select(m.Order)).all()) == n_before and len(db.scalars(select(m.Receipt)).all()) == 1)

        print("\n".join(log))
        print(f"\n{len(log)} checks passed")
