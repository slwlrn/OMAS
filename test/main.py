# main.py
import logging
import os
import secrets
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, g
from sqlalchemy import (
    create_engine, Column, BigInteger, Integer, String, Text, Date, DateTime, Time,
    Enum, ForeignKey, Boolean, Numeric, JSON, func
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import IntegrityError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ========= Config =========
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:123456@localhost:3306/omasdb"
)
DEMO_LOGIN_PIN = os.getenv("DEMO_LOGIN_PIN", "4321")
SESSION_DURATION_MINUTES = int(os.getenv("SESSION_DURATION_MINUTES", "60"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

logger = logging.getLogger(__name__)


# ========= Sesiones ligeras =========
SESSIONS = {}


def _cleanup_sessions():
    now = datetime.utcnow()
    expired_tokens = [token for token, data in SESSIONS.items() if data["expires_at"] <= now]
    for token in expired_tokens:
        SESSIONS.pop(token, None)


def _session_payload(session_data):
    payload = {k: v for k, v in session_data.items() if k != "expires_at"}
    payload["expires_at"] = serialize_value(session_data["expires_at"])
    return payload


def _resolve_session(token):
    if not token:
        return None
    _cleanup_sessions()
    session_data = SESSIONS.get(token)
    if not session_data:
        return None
    if session_data["expires_at"] <= datetime.utcnow():
        SESSIONS.pop(token, None)
        return None
    return session_data


def create_session(user_type: str, user_obj):
    token = secrets.token_urlsafe(32)
    if user_type == "patient":
        user_id = user_obj.patient_id
        display_name = f"{user_obj.first_name} {user_obj.last_name}".strip()
    else:
        user_id = user_obj.provider_id
        display_name = getattr(user_obj, "display_name", None) or user_obj.email

    session_data = {
        "token": token,
        "user_type": user_type,
        "user_id": user_id,
        "display_name": display_name,
        "email": user_obj.email,
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_DURATION_MINUTES),
    }
    SESSIONS[token] = session_data
    return session_data


def get_session_from_request():
    token = request.headers.get("X-Session-Token") or request.args.get("session_token")
    session = _resolve_session(token)
    if session:
        g.current_session = session
    return session


def require_auth(allowed_roles=None):
    allowed = set(allowed_roles or []) if allowed_roles else None

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            session = get_session_from_request()
            if not session:
                return jsonify({"error": "Autenticación requerida. Inicia sesión para continuar."}), 401
            if allowed and session["user_type"] not in allowed:
                return jsonify({"error": "No cuentas con permisos para esta operación."}), 403
            return func(*args, **kwargs)

        return wrapper

    return decorator

# ========= Util =========
def serialize_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, time):
        return v.isoformat(timespec="seconds")
    return v

def to_dict(obj):
    return {c.name: serialize_value(getattr(obj, c.name)) for c in obj.__table__.columns}


def normalize_datetime(value):
    """Return a naive datetime instance from supported inputs."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    raise ValueError(f"Unsupported datetime value: {value!r}")


def normalize_date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return date.fromisoformat(value)
    raise ValueError(f"Unsupported date value: {value!r}")


def normalize_time(value):
    if value is None or isinstance(value, time):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if len(value) == 5:
            value = f"{value}:00"
        return time.fromisoformat(value)
    raise ValueError(f"Unsupported time value: {value!r}")


def normalize_numeric(value):
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise ValueError(f"Unsupported numeric value: {value!r}")


def coerce_payload(model, data):
    """Convert string payload values to the SQLAlchemy column python types."""
    for column in model.__table__.columns:
        key = column.name
        if key not in data:
            continue
        value = data[key]
        try:
            if isinstance(column.type, DateTime):
                data[key] = normalize_datetime(value)
            elif isinstance(column.type, Date):
                data[key] = normalize_date(value)
            elif isinstance(column.type, Time):
                data[key] = normalize_time(value)
            elif isinstance(column.type, Numeric):
                data[key] = normalize_numeric(value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for {key}: {exc}") from exc
    return data


def appointment_overlaps(db_session, provider_id, start_at, end_at, exclude_id=None):
    """Return True if the provider already has a blocking appointment."""
    if not all([provider_id, start_at, end_at]):
        return False

    query = db_session.query(Appointment).filter(
        Appointment.provider_id == provider_id,
        Appointment.status.in_(["booked", "rescheduled"]),
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
    )
    if exclude_id is not None:
        query = query.filter(Appointment.appointment_id != exclude_id)
    return query.first() is not None

# ========= Modelos =========
class Patient(Base):
    __tablename__ = "patients"
    patient_id   = Column(BigInteger, primary_key=True, autoincrement=True)
    first_name   = Column(String(80), nullable=False)
    last_name    = Column(String(80), nullable=False)
    email        = Column(String(190), unique=True, nullable=False)
    phone        = Column(String(32))
    date_of_birth= Column(Date)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Provider(Base):
    __tablename__ = "providers"
    provider_id  = Column(BigInteger, primary_key=True, autoincrement=True)
    display_name = Column(String(120), nullable=False)
    specialty    = Column(String(120), nullable=False)
    email        = Column(String(190), unique=True, nullable=False)
    phone        = Column(String(32))
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
    start_at     = Column(DateTime, nullable=False)
    end_at       = Column(DateTime, nullable=False)
    reason       = Column(String(160))
    is_blocking  = Column(Boolean, nullable=False, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
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
    amount         = Column(Numeric(10, 2), nullable=False)
    currency       = Column(String(3), nullable=False, default="MXN")
    status         = Column(Enum("pending","paid","refunded","failed", name="payment_status"),
                            nullable=False, default="pending")
    provider_account = Column(String(120))
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    appointment    = relationship("Appointment")

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    pref_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    user_type   = Column(Enum("patient","provider", name="user_type"), nullable=False)
    user_id     = Column(BigInteger, nullable=False)
    channel     = Column(Enum("email","sms","push", name="notify_channel"), nullable=False)
    lead_minutes= Column(Integer, nullable=False, default=1440)
    enabled     = Column(Boolean, nullable=False, default=True)

class NotificationOutbox(Base):
    __tablename__ = "notifications_outbox"
    notif_id     = Column(BigInteger, primary_key=True, autoincrement=True)
    appointment_id = Column(BigInteger, ForeignKey("appointments.appointment_id"))
    channel      = Column(Enum("email","sms","push", name="outbox_channel"), nullable=False)
    template     = Column(String(80), nullable=False)
    payload      = Column(JSON)
    send_after   = Column(DateTime, nullable=False)
    status       = Column(Enum("queued","sending","sent","failed", name="outbox_status"),
                          nullable=False, default="queued")
    last_error   = Column(Text)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    appointment  = relationship("Appointment")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id   = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_type = Column(Enum("patient","provider","admin","system", name="actor_type"), nullable=False)
    actor_id   = Column(BigInteger)
    action     = Column(String(80), nullable=False)
    entity_type= Column(String(80), nullable=False)
    entity_id  = Column(BigInteger)
    ip         = Column(String(45))
    metadata_  = Column("metadata", JSON)
    event_ts   = Column(DateTime, default=datetime.utcnow)

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
    @require_auth()
    def list_items():
        db = SessionLocal()
        try:
            items = db.query(model).all()
            return jsonify([to_dict(x) for x in items])
        finally:
            db.close()

    @require_auth()
    def create_item():
        data = request.get_json(force=True, silent=False)
        db = SessionLocal()
        try:
            payload = coerce_payload(model, data)
            if model is Appointment:
                start_at = payload.get("start_at")
                end_at = payload.get("end_at")
                provider_id = payload.get("provider_id")
                if not start_at or not end_at:
                    db.rollback()
                    return jsonify({"error": "La cita debe incluir hora de inicio y fin."}), 400
                if start_at >= end_at:
                    db.rollback()
                    return jsonify({"error": "La hora de inicio debe ser anterior a la de fin."}), 400
                if appointment_overlaps(db, provider_id, start_at, end_at):
                    db.rollback()
                    return jsonify({"error": "El proveedor ya tiene una cita reservada en ese horario."}), 409

            obj = model(**payload)
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return jsonify(to_dict(obj)), 201
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": str(e.orig)}), 400
        except ValueError as e:
            db.rollback()
            return jsonify({"error": str(e)}), 400
        finally:
            db.close()

    @require_auth()
    def get_item(pk):
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            return jsonify(to_dict(obj))
        finally:
            db.close()

    @require_auth()
    def update_item(pk):
        data = request.get_json(force=True, silent=False)
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            payload = coerce_payload(model, data)

            if model is Appointment:
                provider_id = payload.get("provider_id", obj.provider_id)
                start_at = payload.get("start_at", obj.start_at)
                end_at = payload.get("end_at", obj.end_at)
                if not start_at or not end_at:
                    db.rollback()
                    return jsonify({"error": "La cita debe incluir hora de inicio y fin."}), 400
                if start_at >= end_at:
                    db.rollback()
                    return jsonify({"error": "La hora de inicio debe ser anterior a la de fin."}), 400
                if appointment_overlaps(db, provider_id, start_at, end_at, exclude_id=pk):
                    db.rollback()
                    return jsonify({"error": "El proveedor ya tiene una cita reservada en ese horario."}), 409

            for k, v in payload.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            db.commit()
            db.refresh(obj)
            return jsonify(to_dict(obj))
        except IntegrityError as e:
            db.rollback()
            return jsonify({"error": str(e.orig)}), 400
        except ValueError as e:
            db.rollback()
            return jsonify({"error": str(e)}), 400
        finally:
            db.close()

    @require_auth()
    def delete_item(pk):
        db = SessionLocal()
        try:
            obj = db.get(model, pk)
            if not obj:
                return jsonify({"error": f"{table} not found"}), 404
            if model is Patient:
                has_active = (
                    db.query(Appointment)
                    .filter(
                        Appointment.patient_id == pk,
                        Appointment.status.in_(["booked", "rescheduled"]),
                    )
                    .first()
                )
                if has_active:
                    db.rollback()
                    return (
                        jsonify({"error": "No se puede eliminar el paciente porque tiene una cita activa."}),
                        400,
                    )

                (
                    db.query(Appointment)
                    .filter(
                        Appointment.patient_id == pk,
                        Appointment.status == "canceled",
                    )
                    .delete(synchronize_session=False)
                )

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


@app.post("/auth/login")
def auth_login():
    data = request.get_json(force=True, silent=False) or {}
    user_type = (data.get("user_type") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()
    pin = str(data.get("pin") or "").strip()

    if user_type not in {"patient", "provider"}:
        return jsonify({"error": "El tipo de usuario debe ser 'patient' o 'provider'."}), 400
    if not email or not pin:
        return jsonify({"error": "Debes indicar email y NIP."}), 400
    if pin != DEMO_LOGIN_PIN:
        logger.warning(
            "Intento de inicio de sesión con NIP inválido | tipo=%s | email=%s",
            user_type or "<desconocido>",
            email or "<desconocido>",
        )
        return jsonify({"error": "El NIP ingresado no es válido."}), 401

    model = Patient if user_type == "patient" else Provider
    db = SessionLocal()
    try:
        user = (
            db.query(model)
            .filter(func.lower(model.email) == email)
            .first()
        )
        if not user:
            return jsonify({"error": "El correo no está registrado."}), 404

        session = create_session(user_type, user)
        return jsonify({"token": session["token"], "user": _session_payload(session)})
    finally:
        db.close()


@app.get("/auth/session")
@require_auth()
def auth_session():
    session = g.get("current_session") or get_session_from_request()
    return jsonify({"user": _session_payload(session)})


@app.post("/auth/logout")
def auth_logout():
    token = request.headers.get("X-Session-Token")
    if not token:
        payload = request.get_json(silent=True) or {}
        token = payload.get("token") if isinstance(payload, dict) else None
    if not token:
        return jsonify({"error": "Debes indicar el token de sesión a cerrar."}), 400
    if token in SESSIONS:
        SESSIONS.pop(token, None)
    return jsonify({"ok": True})


@app.get("/providers/<int:provider_id>/availability")
@require_auth()
def provider_availability(provider_id):
    db = SessionLocal()
    try:
        provider = db.get(Provider, provider_id)
        if not provider:
            return jsonify({"error": "El proveedor solicitado no existe."}), 404

        weekly = (
            db.query(ProviderAvailability)
            .filter(ProviderAvailability.provider_id == provider_id)
            .order_by(ProviderAvailability.weekday, ProviderAvailability.start_time)
            .all()
        )

        exceptions = (
            db.query(ProviderException)
            .filter(ProviderException.provider_id == provider_id)
            .order_by(ProviderException.start_at)
            .all()
        )

        provider_timezone = "UTC"
        tz = timezone.utc
        if provider.timezone:
            try:
                tz = ZoneInfo(provider.timezone)
                provider_timezone = provider.timezone
            except ZoneInfoNotFoundError:
                pass
        now_local = datetime.now(tz)
        now_naive = now_local.replace(tzinfo=None)

        search_days = 14
        slot_minutes = 30
        slot_delta = timedelta(minutes=slot_minutes)

        start_search_date = now_local.date()
        end_search_date = start_search_date + timedelta(days=search_days)

        start_window = datetime.combine(start_search_date, time.min)
        end_window = datetime.combine(end_search_date, time.max)

        busy_appointments = (
            db.query(Appointment)
            .filter(
                Appointment.provider_id == provider_id,
                Appointment.status.in_(["booked", "rescheduled"]),
                Appointment.start_at < end_window,
                Appointment.end_at > start_window,
            )
            .all()
        )

        def to_weekday_candidates(value):
            """Return the Python weekday index (0=Monday) for the stored value."""
            try:
                weekday_value = int(value)
            except (TypeError, ValueError):
                return []

            # UI almacena 1-7 (lunes-domingo). Normalizamos a 0-6 para
            # compararlo con datetime.weekday(). Si ya está en 0-6 lo usamos tal cual.
            if 1 <= weekday_value <= 7:
                weekday_value = (weekday_value - 1) % 7

            if 0 <= weekday_value <= 6:
                return [weekday_value]

            return []

        def overlaps(start_a, end_a, start_b, end_b):
            return start_a < end_b and end_a > start_b

        blocking_exceptions = [exc for exc in exceptions if exc.is_blocking is not False]

        busy_ranges = []
        for appointment in busy_appointments:
            busy_ranges.append((appointment.start_at, appointment.end_at))
        for exception in blocking_exceptions:
            busy_ranges.append((exception.start_at, exception.end_at))

        upcoming_slots = []

        weekly_rules = list(weekly)

        for day_offset in range(search_days + 1):
            current_date = start_search_date + timedelta(days=day_offset)
            current_weekday = current_date.weekday()

            matching_rules = [
                rule
                for rule in weekly_rules
                if current_weekday in to_weekday_candidates(rule.weekday)
            ]

            if not matching_rules:
                continue

            for rule in matching_rules:
                if not isinstance(rule.start_time, time) or not isinstance(rule.end_time, time):
                    continue

                rule_start = datetime.combine(current_date, rule.start_time)
                rule_end = datetime.combine(current_date, rule.end_time)

                current_slot_start = rule_start
                while current_slot_start + slot_delta <= rule_end:
                    current_slot_end = current_slot_start + slot_delta

                    if current_slot_end <= now_naive:
                        current_slot_start += slot_delta
                        continue

                    is_busy = any(
                        overlaps(current_slot_start, current_slot_end, busy_start, busy_end)
                        for busy_start, busy_end in busy_ranges
                    )
                    if not is_busy:
                        upcoming_slots.append(
                            {
                                "start_at": serialize_value(current_slot_start),
                                "end_at": serialize_value(current_slot_end),
                                "date": serialize_value(current_date),
                                "weekday": current_weekday,
                                "slot_minutes": slot_minutes,
                            }
                        )

                    current_slot_start += slot_delta

        upcoming_slots.sort(key=lambda slot: slot["start_at"])

        return jsonify(
            {
                "provider": to_dict(provider),
                "weekly": [to_dict(item) for item in weekly],
                "exceptions": [to_dict(item) for item in exceptions],
                "upcoming_slots": upcoming_slots,
                "timezone": provider_timezone,
            }
        )
    finally:
        db.close()


@app.post("/appointments/<int:pk>/cancel")
@require_auth()
def cancel_appointment(pk):
    db = SessionLocal()
    try:
        appointment = db.get(Appointment, pk)
        if not appointment:
            db.rollback()
            return jsonify({"error": "La cita solicitada no existe."}), 404
        if appointment.status == "canceled":
            db.rollback()
            return jsonify(to_dict(appointment))
        appointment.status = "canceled"
        db.commit()
        db.refresh(appointment)
        return jsonify(to_dict(appointment))
    finally:
        db.close()


@app.get("/")
def serve_frontend():
    """Devuelve el frontend estático para que Waitress lo sirva junto al API."""
    return send_from_directory(APP_DIR, FRONTEND_ENTRY)


@app.get("/frontend.js")
def serve_frontend_bundle():
    """Expone el bundle JS principal que consume la API desde el mismo host."""
    return send_from_directory(APP_DIR, "frontend.js")


@app.get("/api")
def api_root():
    return jsonify({
        "ok": True,
        "message": "OMAS Flask Monolith",
        "resources": [p for p, _, _ in RESOURCES]
    })

if __name__ == "__main__":
    app.run(debug=True)
