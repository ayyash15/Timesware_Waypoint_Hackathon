import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
DATA_DIR = os.getenv("DATA_DIR", "/data")
FRONTEND_DIR = os.getenv("FRONTEND_DIR", "/frontend")
DEMO_DATE = os.getenv("DEMO_DATE", "2026-10-06")        # the seeded delivery day
DEMAND_SCALE = float(os.getenv("DEMAND_SCALE", "1.0"))  # raise to make the seeded day more over-capacity
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "Waypoint@2026")
# The Designathon has no login screen (the Home hub is the role picker), so each role page signs in as that
# role's seeded demo account. Set DEMO_LOGIN=0 to disable this and require POST /api/auth/login.
DEMO_LOGIN = os.getenv("DEMO_LOGIN", "1") == "1"
