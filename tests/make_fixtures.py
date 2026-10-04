"""Writes SYNTHETIC CSVs in the competition schema, for tests only.
These are NOT the real competition datasets (which must stay in the private repo's data/ folder)."""
import csv, os, sys

out = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures"
os.makedirs(out, exist_ok=True)


def w(name, header, rows):
    with open(os.path.join(out, name), "w", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)


# --- outlets: 24 Fresh, 6 Style, 6 Tech in Peliyagoda; a few van-only and mall outlets
outlets = []
n = 0
for dist, count in (("Colombo", 14), ("Gampaha", 10)):
    for i in range(count):
        n += 1
        van_only = i % 7 == 3
        mall = i % 9 == 4
        outlets.append([f"OUT{n:03d}", "Fresh", dist, "Peliyagoda", "rear_dock" if not mall else "mall_bay",
                        "van_only" if van_only else "none", "06:00-07:30" if mall else "", "05:00", "08:00"])
for i in range(6):
    n += 1
    outlets.append([f"OUT{n:03d}", "Style", "Colombo", "Peliyagoda", "street", "none", "", "09:00", "17:00"])
for i in range(6):
    n += 1
    outlets.append([f"OUT{n:03d}", "Tech", "Gampaha", "Peliyagoda", "rear_dock", "none", "", "09:00", "17:00"])
for i in range(3):
    n += 1
    outlets.append([f"OUT{n:03d}", "Fresh", "Kandy", "Kandy", "rear_dock", "none", "", "05:00", "08:00"])
w("outlets.csv", ["outlet_id", "brand", "district", "depot", "dock_type", "parking_constraint", "mall_window",
                  "window_open_time", "window_close_time"], outlets)

veh = []
v = 0
for _ in range(4):
    v += 1; veh.append([f"VEH{v:03d}", "truck", "reefer", 6000, 28, "diesel", 4.5, 900, "Peliyagoda"])
for _ in range(3):
    v += 1; veh.append([f"VEH{v:03d}", "truck", "ambient", 7000, 32, "diesel", 4.0, 900, "Peliyagoda"])
for _ in range(3):
    v += 1; veh.append([f"VEH{v:03d}", "van", "ambient", 1500, 9, "petrol", 9.0, 400, "Peliyagoda"])
for _ in range(2):
    v += 1; veh.append([f"VEH{v:03d}", "truck", "reefer", 5000, 22, "diesel", 4.5, 900, "Kandy"])
w("vehicles.csv", ["vehicle_id", "type", "temp", "weight_cap_kg", "volume_cap_m3", "fuel_type", "km_per_l",
                   "weekly_fuel_quota_l", "depot"], veh)

import datetime as dt
cal = []
d0 = dt.date(2026, 10, 1)
for i in range(21):
    d = d0 + dt.timedelta(days=i)
    iso = d.isocalendar()
    cal.append([d.isoformat(), d.weekday(), iso[0], iso[1], 1 if d.day in (25, 26) else 0, "", 0, 0,
                0 if d.weekday() == 6 else 1])
w("calendar.csv", ["date", "dow", "iso_year", "iso_week", "is_payday", "festival", "festival_ramp", "monsoon",
                   "is_operating"], cal)

w("district_travel.csv", ["district", "depot", "depot_to_district_km", "depot_to_district_freeflow_min",
                          "inter_stop_km", "inter_stop_freeflow_min"],
  [["Colombo", "Peliyagoda", 12, 30, 3, 9], ["Gampaha", "Peliyagoda", 25, 45, 6, 12], ["Kandy", "Kandy", 6, 15, 2, 7]])

w("service_allowance.csv", ["brand", "dock_type", "service_allowance_min"],
  [[b, dk, mins] for b in ("Fresh", "Style", "Tech") for dk, mins in (("rear_dock", 15), ("street", 10), ("mall_bay", 25))])
print("fixtures written to", out)
