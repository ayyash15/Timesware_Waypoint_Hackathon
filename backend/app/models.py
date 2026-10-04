from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

BigText = Text().with_variant(MEDIUMTEXT(), "mysql")   # proof-of-delivery photos are base64 (> 64 KB TEXT limit)
from .db import Base


def now():
    return datetime.utcnow()


# ---------- reference data (seeded from the shared CSVs) ----------
class Outlet(Base):
    __tablename__ = "outlets"
    outlet_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    brand: Mapped[str] = mapped_column(String(10))
    district: Mapped[str] = mapped_column(String(40))
    depot: Mapped[str] = mapped_column(String(20))
    dock_type: Mapped[str] = mapped_column(String(20))
    parking_constraint: Mapped[str] = mapped_column(String(20))
    mall_window: Mapped[str | None] = mapped_column(String(20), nullable=True)
    window_open_time: Mapped[str] = mapped_column(String(5))
    window_close_time: Mapped[str] = mapped_column(String(5))


class Vehicle(Base):
    __tablename__ = "vehicles"
    vehicle_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    type: Mapped[str] = mapped_column(String(10))
    temp: Mapped[str] = mapped_column(String(10))
    weight_cap_kg: Mapped[float] = mapped_column(Float)
    volume_cap_m3: Mapped[float] = mapped_column(Float)
    fuel_type: Mapped[str] = mapped_column(String(20))
    km_per_l: Mapped[float] = mapped_column(Float)
    weekly_fuel_quota_l: Mapped[float] = mapped_column(Float)
    depot: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15), default="available")   # available | in_workshop


class CalendarDay(Base):
    __tablename__ = "calendar_days"
    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    dow: Mapped[int] = mapped_column(Integer)
    iso_year: Mapped[int] = mapped_column(Integer)
    iso_week: Mapped[int] = mapped_column(Integer)
    is_payday: Mapped[int] = mapped_column(Integer)
    festival: Mapped[str | None] = mapped_column(String(60), nullable=True)
    festival_ramp: Mapped[float] = mapped_column(Float, default=0)
    monsoon: Mapped[int] = mapped_column(Integer, default=0)
    is_operating: Mapped[int] = mapped_column(Integer, default=1)


class DistrictTravel(Base):
    __tablename__ = "district_travel"
    district: Mapped[str] = mapped_column(String(40), primary_key=True)
    depot: Mapped[str] = mapped_column(String(20))
    depot_to_district_km: Mapped[float] = mapped_column(Float)
    depot_to_district_freeflow_min: Mapped[float] = mapped_column(Float)
    inter_stop_km: Mapped[float] = mapped_column(Float)
    inter_stop_freeflow_min: Mapped[float] = mapped_column(Float)


class ServiceAllowance(Base):
    __tablename__ = "service_allowance"
    brand: Mapped[str] = mapped_column(String(10), primary_key=True)
    dock_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    service_allowance_min: Mapped[float] = mapped_column(Float)


# ---------- people ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(15))          # dispatcher | loader | driver | store
    display_name: Mapped[str] = mapped_column(String(80))
    depot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outlet_id: Mapped[str | None] = mapped_column(ForeignKey("outlets.outlet_id"), nullable=True)
    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.vehicle_id"), nullable=True)


# ---------- workflow ----------
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(30), unique=True)
    outlet_id: Mapped[str] = mapped_column(ForeignKey("outlets.outlet_id"))
    brand: Mapped[str] = mapped_column(String(10))
    district: Mapped[str] = mapped_column(String(40))
    depot: Mapped[str] = mapped_column(String(20))
    delivery_date: Mapped[str] = mapped_column(String(10))
    temp_requirement: Mapped[str] = mapped_column(String(10))
    order_units: Mapped[int] = mapped_column(Integer)
    order_weight_kg: Mapped[float] = mapped_column(Float)
    order_volume_m3: Mapped[float] = mapped_column(Float)
    # confirmed -> planned -> loaded -> in_transit -> delivered|failed -> received|issue ; or deferred
    status: Mapped[str] = mapped_column(String(15), default="confirmed")
    deferred_yesterday: Mapped[int] = mapped_column(Integer, default=0)
    days_since_last_served: Mapped[int] = mapped_column(Integer, default=0)
    items_json: Mapped[str | None] = mapped_column(Text, nullable=True)   # [{name, qty}] entered on the order form
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    outlet = relationship("Outlet")


class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_date: Mapped[str] = mapped_column(String(10))
    depot: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), default="draft")      # draft | published
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON string


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.vehicle_id"))
    trip_no: Mapped[int] = mapped_column(Integer)
    brand: Mapped[str] = mapped_column(String(10))
    district: Mapped[str] = mapped_column(String(40))
    depot: Mapped[str] = mapped_column(String(20))
    depart_time: Mapped[str] = mapped_column(String(5))
    minutes: Mapped[float] = mapped_column(Float)
    fuel_l: Mapped[float] = mapped_column(Float)
    volume_m3: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(15), default="planned")     # planned|loading|ready|departed|completed
    stops = relationship("TripStop", back_populates="trip", order_by="TripStop.seq")


class TripStop(Base):
    __tablename__ = "trip_stops"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    seq: Mapped[int] = mapped_column(Integer)
    eta: Mapped[str] = mapped_column(String(5))
    window: Mapped[str] = mapped_column(String(11))
    status: Mapped[str] = mapped_column(String(12), default="pending")     # pending|delivered|partial|failed|cancelled
    time_in: Mapped[str | None] = mapped_column(String(5), nullable=True)
    time_out: Mapped[str | None] = mapped_column(String(5), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pod_photo: Mapped[str | None] = mapped_column(BigText, nullable=True)     # small base64 data URL
    client_uuid: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # device clock
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    conflict_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    loaded: Mapped[int] = mapped_column(Integer, default=0)      # loader ticked this stop onto the vehicle
    trip = relationship("Trip", back_populates="stops")
    order = relationship("Order")


class Deferral(Base):
    __tablename__ = "deferrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    reason_code: Mapped[str] = mapped_column(String(40))
    reason_text: Mapped[str] = mapped_column(Text)
    unavoidable: Mapped[bool] = mapped_column(Boolean, default=False)
    decided_by: Mapped[str] = mapped_column(String(40), default="engine")  # engine | dispatcher username
    override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rescheduled_for: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    order = relationship("Order")


class LoadingIssue(Base):
    __tablename__ = "loading_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    issue_type: Mapped[str] = mapped_column(String(20))        # missing | damaged | short
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    status: Mapped[str] = mapped_column(String(10))            # confirmed | issue
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(15))
    outlet_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    vehicle_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
