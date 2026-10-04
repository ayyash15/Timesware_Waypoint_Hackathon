# Timesware - Waypoint (Tech-Triathlon 2026)

Team Timesware's submission for Tech-Triathlon 2026: a delivery planning system for **Waypoint Group** (3 brands, 120 outlets, 60 vehicles, 2 depots). Three phases, scored independently.

| Phase | Status |
|---|---|
| Designathon | Submitted. Design document: [`designathon/Timesware_Designathon.md`](designathon/Timesware_Designathon.md) |
| **Hackathon** | **This repository: the Designathon frontend wired to a FastAPI + MySQL backend.** |
| Datathon | Not started in this repo. |

## 1. Run it

Prerequisite: Docker with Compose.

```bash
docker compose up --build        # no .env needed; `cp .env.example .env` only to override defaults
```

Open <http://localhost:8000/> (Home = role picker). API console: <http://localhost:8000/docs>.
The first start creates the tables and seeds the shared datasets plus one delivery day (`DEMO_DATE`). To re-seed from scratch: `docker compose down -v && docker compose up --build`.

**Datasets.** The competition CSVs are confidential and are **not in git**. Put `outlets.csv`, `vehicles.csv`, `calendar.csv`, `district_travel.csv`, `service_allowance.csv` in `data/` (git-ignored) before starting. If they are missing, the seed script falls back to a small **synthetic** sample set with the same schema (`backend/app/sample_data/`), so the stack still runs. No data is sent to any external service.

### Configuration (`.env.example`)

| Variable | Purpose | Default |
|---|---|---|
| `MYSQL_*` | database name, user, passwords | `waypoint` ... |
| `SECRET_KEY` | JWT signing key - **change it** | placeholder |
| `SEED_PASSWORD` | password of the four seeded accounts | `Waypoint@2026` |
| `DEMO_DATE` | the seeded delivery day | `2026-10-06` |
| `DEMAND_SCALE` | multiplies seeded order sizes; raise it for a more over-capacity day | `1.8` |
| `WORKSHOP_COUNT` | vehicles in the workshop on the demo day | `4` |
| `ENFORCE_CUTOFF` | `1` = orders after 16:00 Sri Lanka time roll to the next run | `0` (judges can order at any hour) |
| `DEMO_LOGIN` | `1` = each role page signs in as its seeded account (see section 5) | `1` |

## 2. Seeded accounts

| Role | Username | Password | Opens at |
|---|---|---|---|
| Dispatcher | `dispatcher` | `Waypoint@2026` | `/dispatcher-overview.html` |
| Loader | `loader` | `Waypoint@2026` | `/loader-dock.html` |
| Driver | `driver` | `Waypoint@2026` | `/driver-stops.html` |
| Store manager | `store` | `Waypoint@2026` | `/store-order.html` |

The Designathon has no login screen (the Home hub is the role picker), so choosing a role card on Home signs you in as that account automatically. The username/password pairs work on `POST /api/auth/login` (use them in `/docs`). Set `DEMO_LOGIN=0` to disable the automatic sign-in on a public deployment.

## 3. Judge walkthrough

Use a desktop window for Dispatcher and Store; use a phone-sized window (or browser device mode) for Loader and Driver. One browser is fine: each role page signs in as its own account.

1. **Store manager** - Home -> *Store Manager* -> **Place Order**. Enter quantities (for example 10 dairy, 6 produce) and **Submit Order**. The confirmation shows the real order reference. *(Do this before step 3 so the order is part of today's plan.)*
2. **Dispatcher** - Home -> *Dispatcher* -> **Overview**: the closed order queue for the delivery day with temperature, volume, window and access, including the new order.
3. **Plan and allocate** - **Planning**. The first visit runs the allocation: trips per vehicle in the centre (capacity and trip-time meters), the **capacity shortfall banner** with the binding constraint, the waiting pool of **deferred** orders on the left, and the engine's plain-English reason for each deferral on the right.
4. Pick a waiting order: **Assign** re-validates the whole plan and either places it or refuses with the reasons; **Defer** asks for a reason and records it.
5. **Review Deferrals** -> **Deferral Summary** (reason, deferred yesterday, days since last served, next run) -> **Commit Plan**. The plan is published and locked; loader, drivers and outlets are notified. You land on **Live Operations**.
6. **Store manager** (optional) - **Delivery Status** shows the expected arrival time and the vehicle id (for example "on VEH014"). Remember this vehicle. If your outlet's order was deferred, **See why an order was deferred** shows the deferral notice.
7. **Loader** - Home -> *Loader* -> **Dock Queue** lists the published trips in departure order. Open the **loading list** of the vehicle from step 6 (last stop is loaded first). Use **Flag issue** (Missing / Damaged / Short) on one stop - the dispatcher and the outlet are notified. Tick **Loaded** on every stop; after the last one the vehicle is released to the driver (you are asked to confirm if a flagged issue is still open).
8. **Driver** - Home -> *Driver* -> **Today's stops**. The route of the released vehicle appears. **START STOP** -> stop detail -> **Record Outcome** -> *DELIVERED*, add the proof-of-delivery photo (camera or file) and optionally a signature (receiver name) -> **Confirm Delivery**.
9. **Offline and recovery** - on **Today's stops**, tap the **avatar circle** (RP) at the top to lose signal (or use airplane mode); the setting stays on while you move between driver screens. Record the next stop: the bar reads *OFFLINE - 1 record waiting to sync* and the stop shows *Saved offline*. Tap the bar (or restore the connection): *SYNCING...* then *ALL RECORDS SYNCED*, and the record is on the server. Repeat for the remaining stops (*ATTEMPTED* needs a note and records a failed delivery).
10. **Dispatcher** - **Live Operations** shows vehicle progress, issues and completion (refreshes every 8 seconds).
11. **Store manager** - **Delivery Status** shows *Delivered*; open **Confirm Receipt** and either **Confirm Receipt** or **Report discrepancy**.

## 4. Architecture

```
 Browser  ->  Designathon pages (static HTML/CSS/JS, served by FastAPI at /)
              |-- <script src="js/data.js">  ->  GET /js/data.js   (generated from the database)
              |-- <script src="js/wp-live.js"> -> fetch /api/...    (JWT per role; local queue on the driver phone)
                                  v
 FastAPI (Python 3.12): auth | dispatcher | loader | driver | store routers -> services -> engine.py (allocate, validate, layout)
                                  v
 SQLAlchemy -> MySQL 8   (SQLite for the tests)
```

Details and diagrams: [`docs/architecture.md`](docs/architecture.md), [`docs/data-model.md`](docs/data-model.md). AI disclosure: [`docs/ai-disclosure.md`](docs/ai-disclosure.md).

Repository layout: `frontend/` (the Designathon prototype + `js/wp-live.js`), `backend/app/`, `docs/`, `data/` (CSVs, git-ignored), `tests/`, `docker-compose.yml`, `.env.example`.

## 5. Allocation rules (`backend/app/engine.py`)

Chilled orders need a reefer (reefers also carry ambient); `van_only` outlets need a van; a vehicle serves only its home depot and only if available; orders are never split; weight **and** volume capacity per trip; at most 2 trips per vehicle; one brand + district per trip; Fresh trips share a 270-minute budget (03:30-08:00) and must arrive inside the delivery window; Style + Tech trips share 480 minutes; mall and outlet windows are intersected; weekly fuel quota counts fuel already used by published plans that week. Trip time = outbound + inter-stop travel + service allowances, exactly as in the booklet. Orders are served by priority (deferred yesterday first, then days since last served, chilled, Fresh); everything else is **deferred with a reason code, the constraint that bound, an explanation and whether it was unavoidable**. `validate_plan` re-checks any hand-edited plan with the same rules. Assumption: Style/Tech trips start at 07:00 (the booklet says only "trading day").

## 6. Offline and reconciliation

Every driver outcome is written to a local queue (`localStorage`) first. With signal, the queue is posted to `POST /api/driver/sync`; the server is idempotent per `client_uuid`, keeps the device timestamp, and applies one conflict rule: a delivery recorded **before** the dispatcher's deferral stands, one recorded after is rejected and flagged to the dispatcher.

## 7. Significant departures from the Designathon submission

The screens, layout, navigation and visual language are unchanged. Differences:

- **No login screen was added** (the design's Home hub is the role picker). Role pages auto-sign-in as the seeded account (`DEMO_LOGIN`); real login is available through the API.
- **Planning screen:** the static example trips were replaced by the real plan's trips; the "+ Add another vehicle" placeholder card was removed (Assign picks a valid vehicle automatically).
- **Live Operations:** the "At stop" tile is relabelled **Loading / queued** because the backend tracks stops per trip, not GPS position.
- **Place Order:** the form asks only for quantities, so weight and volume are estimated per brand; the brand selector is locked to the signed-in outlet's brand.
- **Driver:** *ATTEMPTED* is stored as a failed delivery and *ISSUE* as a partial delivery (both need a note; partial also needs a photo); the signature box captures the receiver's name. Tapping the avatar on Today's stops toggles a **simulated offline mode** for demos (real offline also works).
- **Orders cutoff:** the 4 PM cutoff is not enforced by default (`ENFORCE_CUTOFF=1` enables it).
- **Capacity Planning** is derived from the day's confirmed demand, not from the Datathon forecast.
- Outlet names do not exist in the CSVs, so outlet IDs are shown where the prototype showed names.
- The prototype moved from `docs/` to `frontend/` because `docs/` is reserved for architecture, data model and AI disclosure. A GitHub Pages copy of the static prototype (read-only mock) would need to be redeployed from `frontend/`.

## 8. Tests

```bash
pip install -r backend/requirements.txt pytest httpx
python -m pytest -q tests/test_e2e.py            # API: all four roles, constraints verified from the database, offline sync, conflicts
# browser-level: start the server on a fresh SQLite DB, then
cd tests/browser && npm install && BASE=http://127.0.0.1:8123 node flow.test.mjs
```

The tests use SQLite and **synthetic** CSVs (`tests/fixtures`, generated by `tests/make_fixtures.py`).

## 9. Known limitations

- `docker compose up` and the MySQL path were **not run in the build sandbox** (no Docker there); only SQLite and synthetic data were exercised. Run the Docker check first; if the seed raises a `KeyError`, a CSV header differs from the booklet.
- Responsive behaviour was checked structurally, not on a physical phone.
- `GET /js/data.js` is unauthenticated (the prototype has no login) and shows the depot-level view of `DEMO_DATE`.
- Proof-of-delivery photos are stored as small base64 text in the database; there is no photo viewer for the dispatcher.
- Reason attribution for capacity deferrals is heuristic (`FLEET_CAPACITY` is the catch-all).

## Team
Timesware
