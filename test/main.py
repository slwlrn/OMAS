# main.py
import os
from datetime import datetime, date, time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import (
    create_engine, Column, BigInteger, Integer, String, Text, Date, DateTime, Time,
    Enum, ForeignKey
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import IntegrityError

# ========= Config =========
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:123456@localhost:3306/omasdb"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# ========= Util =========
def serialize_value(v):
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.isoformat(timespec="seconds")
    return v

def to_dict(obj):
    return {c.name: serialize_value(getattr(obj, c.name)) for c in obj.__table__.columns}

# ========= Modelos =========
class Patient(Base):
    __tablename__ = "patients"
    patient_id   = Column(BigInteger, primary_key=True, autoincrement=True)
    first_name   = Column(String(80), nullable=False)
    last_name    = Column(String(80), nullable=False)
    email        = Column(String(120), unique=True, nullable=False)
    phone        = Column(String(40))
    date_of_birth= Column(Date)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Provider(Base):
    __tablename__ = "providers"
    provider_id  = Column(BigInteger, primary_key=True, autoincrement=True)
    display_name = Column(String(120), nullable=False)
    name         = Column(String(120))
    specialty    = Column(String(120))
    phone        = Column(String(40))
    timezone     = Column(String(64), default="UTC")
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProviderAvailability(Base):
    __tablename__ = "provider_availability"
    availability_id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id     = Column(BigInteger, ForeignKey("providers.provider_id"), nullable=False)
    weekday         = Column(Integer, nullable=False)
    start_time      = Column(Time, nullable=False)
    end_time        = Column(Time, nullable=False)
    location        = Column(String(120))
    provider        = relationship("Provider")

class ProviderException(Base):
    __tablename__ = "provider_exceptions"
    exception_id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id  = Column(BigInteger, ForeignKey("providers.provider_id"), nullable=False)
    start_time   = Column(DateTime, nullable=False)
    end_time     = Column(DateTime, nullable=False)
    reason       = Column(String(200))
    provider     = relationship("Provider")

class Appointment(Base):
    __tablename__ = "appointments"
    appointment_id = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id     = Column(BigInteger, ForeignKey("patients.patient_id"), nullable=False)
    provider_id    = Column(BigInteger, ForeignKey("providers.provider_id"), nullable=False)
    start_at       = Column(DateTime, nullable=False)
    end_at         = Column(DateTime, nullable=False)
    status         = Column(Enum("booked","rescheduled","canceled","completed","no_show",
                                 name="appointment_status"), nullable=False, default="booked")
    outcome_note   = Column(String(500))
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient        = relationship("Patient")
    provider       = relationship("Provider")

class Payment(Base):
    __tablename__ = "payments"
    payment_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.appointment_id"))
    amount_cents   = Column(Integer, nullable=False, default=0)
    currency       = Column(String(3), nullable=False, default="MXN")
    status         = Column(Enum("pending","paid","failed","refunded", name="payment_status"),
                            nullable=False, default="pending")
    method         = Column(String(40))
    provider_txn_id= Column(String(120))
    created_at     = Column(DateTime, default=datetime.utcnow)
    appointment    = relationship("Appointment")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    pref_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    user_type   = Column(Enum("patient","provider", name="user_type"), nullable=False)
    user_id     = Column(BigInteger, nullable=False)
    channel     = Column(Enum("email","sms","push", name="notify_channel"), nullable=False)
    lead_minutes= Column(Integer, nullable=False, default=120)

class NotificationOutbox(Base):
    __tablename__ = "notifications_outbox"
    notif_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.appointment_id"))
    target       = Column(String(255))
    channel      = Column(Enum("email","sms","push", name="outbox_channel"), nullable=False)
    payload      = Column(Text)
    status       = Column(Enum("pending","sent","failed", name="outbox_status"), default="pending")
    last_error   = Column(Text)
    created_at   = Column(DateTime, default=datetime.utcnow)
    sent_at      = Column(DateTime)
    appointment  = relationship("Appointment")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id   = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_id   = Column(BigInteger)
    action     = Column(String(120), nullable=False)
    entity     = Column(String(80))
    entity_id  = Column(BigInteger)
    ts         = Column(DateTime, default=datetime.utcnow)
    details    = Column(Text)

# ========= Flask + CRUD genérico =========
APP_DIR = Path(__file__).resolve().parent
FRONTEND_ENTRY = "frontend.html"

app = Flask(__name__)

RESOURCES = [
    ("/patients",                Patient,               "patient_id"),
    ("/providers",               Provider,              "provider_id"),
    ("/provider-availability",   ProviderAvailability,  "availability_id"),
    ("/provider-exceptions",     ProviderException,     "exception_id"),
    ("/appointments",            Appointment,           "appointment_id"),
    ("/payments",                Payment,               "payment_id"),
    ("/notification-preferences",NotificationPreference,"pref_id"),
    ("/notifications-outbox",    NotificationOutbox,    "notif_id"),
    ("/audit-logs",              AuditLog,              "audit_id"),
]

def register_crud(path: str, model, pk_column: str):
    table = model.__tablename__

    # ----- handlers -----
    def list_items():
        db = SessionLocal()
        try:
            items = db.query(model).all()
            return jsonify([to_dict(x) for x in items])
        finally:
            db.close()

    def create_item():
        data = request.get_json(force=True, silent=False)
        db = SessionLocal()
        try:
            obj = model(**data)
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return jsonify(to_dict(obj)), 201
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": str(e.orig)}), 400
        finally:
            db.close()

    def get_item(pk):
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            return jsonify(to_dict(obj))
        finally:
            db.close()

    def update_item(pk):
        data = request.get_json(force=True, silent=False)
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            for k, v in data.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            db.commit()
            db.refresh(obj)
            return jsonify(to_dict(obj))
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": str(e.orig)}), 400
        finally:
            db.close()

    def delete_item(pk):
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            db.delete(obj)
            db.commit()
            return "", 204
        finally:
            db.close()

    # ----- rutas -----
    app.add_url_rule(path,               endpoint=f"{table}_list",   view_func=list_items,  methods=["GET"])
    app.add_url_rule(path,               endpoint=f"{table}_create", view_func=create_item, methods=["POST"])
    app.add_url_rule(f"{path}/<int:pk>", endpoint=f"{table}_get",    view_func=get_item,    methods=["GET"])
    app.add_url_rule(f"{path}/<int:pk>", endpoint=f"{table}_update", view_func=update_item, methods=["PUT"])
    app.add_url_rule(f"{path}/<int:pk>", endpoint=f"{table}_delete", view_func=delete_item, methods=["DELETE"])

for path, model, pk in RESOURCES:
    register_crud(path, model, pk)

@app.get("/")
def serve_frontend():
    """Devuelve el frontend estático para que Waitress lo sirva junto al API."""
    return send_from_directory(APP_DIR, FRONTEND_ENTRY)


@app.get("/api")
def api_root():
    return jsonify({
        "ok": True,
        "message": "OMAS Flask Monolith",
        "resources": [p for p, _, _ in RESOURCES]
    })

if __name__ == "__main__":
    app.run(debug=True)
