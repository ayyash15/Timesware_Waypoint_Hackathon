import os
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .config import DEMO_DATE, FRONTEND_DIR
from .db import get_db
from .seed import seed_if_empty
from .wpdata import build_wp_data, render_data_js
from . import auth, dispatcher, loader, driver, store

app = FastAPI(title="Waypoint Delivery Planning API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth, dispatcher, loader, driver, store):
    app.include_router(r.router)


@app.on_event("startup")
def startup():
    print("[seed]", seed_if_empty())


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/wp-data")
def wp_data(date: str = DEMO_DATE, vehicle_id: str | None = None, trip_no: int | None = None, db: Session = Depends(get_db)):
    """The WP_DATA object the prototype consumes, as JSON."""
    return build_wp_data(db, date, vehicle_id=vehicle_id, trip_no=trip_no)


# The locked prototype loads <script src="js/data.js">. Serving that exact path from the
# database means the unmodified static pages render real backend data.
# Registered BEFORE the static mount so it takes precedence over the original mock file.
@app.get("/js/data.js")
def data_js(request: Request, date: str = DEMO_DATE, vehicle_id: str | None = None, trip_no: int | None = None,
            db: Session = Depends(get_db)):
    # static pages load a plain <script src="js/data.js">; the loader's / driver's chosen vehicle and trip travel in
    # two cookies set by js/wp-live.js (wp_vehicle, wp_trip).
    vehicle_id = vehicle_id or request.cookies.get("wp_vehicle") or None
    c = request.cookies.get("wp_trip")
    trip_no = trip_no if trip_no is not None else (int(c) if c and c.isdigit() else None)
    body = render_data_js(build_wp_data(db, date, vehicle_id=vehicle_id, trip_no=trip_no))
    return Response(body, media_type="application/javascript; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
