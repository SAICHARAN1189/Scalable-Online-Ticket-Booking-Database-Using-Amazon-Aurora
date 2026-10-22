"""
Aurora Ticket Booking — Flask Application
==========================================
Routes writes to the Aurora writer endpoint and reads to the reader endpoint.
Falls back to a local SQLite database for offline development/testing.
"""

import os
import time
import uuid
import sqlite3
import json
from datetime import datetime, timezone
from contextlib import contextmanager
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, flash, g
)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-insecure-key-change-me")

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
USE_LOCAL_DB = os.getenv("USE_LOCAL_DB", "true").lower() == "true"

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "local_ticket_booking.db")

# Aurora endpoints (used only when USE_LOCAL_DB is False)
AURORA_WRITER_HOST = os.getenv("AURORA_WRITER_HOST", "")
AURORA_READER_HOST = os.getenv("AURORA_READER_HOST", "")
AURORA_PORT = int(os.getenv("AURORA_PORT", "5432"))
AURORA_DB_NAME = os.getenv("AURORA_DB_NAME", "postgres")
AURORA_USERNAME = os.getenv("AURORA_USERNAME", "postgres")
AURORA_PASSWORD = os.getenv("AURORA_PASSWORD", "")
USE_IAM_AUTH = os.getenv("USE_IAM_AUTH", "true").lower() == "true"
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")


def _get_pg_conn(host):
    """Create a PostgreSQL connection to the given Aurora endpoint using IAM or password auth."""
    import psycopg2
    db_user = AURORA_USERNAME or "postgres"

    # 1. Attempt IAM Database Authentication if enabled
    if USE_IAM_AUTH:
        try:
            import boto3
            rds_client = boto3.client("rds", region_name=AWS_REGION)
            token = rds_client.generate_db_auth_token(
                DBHostname=host,
                Port=AURORA_PORT,
                DBUsername=db_user,
                Region=AWS_REGION,
            )
            return psycopg2.connect(
                host=host,
                port=AURORA_PORT,
                dbname=AURORA_DB_NAME or "postgres",
                user=db_user,
                password=token,
                sslmode="require",
                connect_timeout=15,
            )
        except Exception as iam_err:
            if not AURORA_PASSWORD:
                raise RuntimeError(f"IAM DB Authentication failed: {iam_err}") from iam_err

    # 2. Fall back to master password if IAM is disabled or unconfigured
    return psycopg2.connect(
        host=host,
        port=AURORA_PORT,
        dbname=AURORA_DB_NAME or "postgres",
        user=db_user,
        password=AURORA_PASSWORD,
        sslmode="require",
        connect_timeout=15,
    )


def _get_sqlite_conn():
    """Return a SQLite connection (local development mode)."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Connection helpers with activity logging
# ---------------------------------------------------------------------------
@contextmanager
def get_writer_conn():
    """Get a database connection routed to the WRITER endpoint."""
    if USE_LOCAL_DB:
        conn = _get_sqlite_conn()
    else:
        conn = _get_pg_conn(AURORA_WRITER_HOST)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_reader_conn():
    """Get a database connection routed to the READER endpoint."""
    if USE_LOCAL_DB:
        conn = _get_sqlite_conn()
    else:
        conn = _get_pg_conn(AURORA_READER_HOST)
    try:
        yield conn
    finally:
        conn.close()


def log_activity(conn, operation, endpoint, query_type, duration_ms):
    """Insert a row into db_activity_log."""
    try:
        cur = conn.cursor()
        if USE_LOCAL_DB:
            cur.execute(
                "INSERT INTO db_activity_log (operation, endpoint_used, query_type, duration_ms) "
                "VALUES (?, ?, ?, ?)",
                (operation, endpoint, query_type, round(duration_ms, 2)),
            )
        else:
            cur.execute(
                "INSERT INTO db_activity_log (operation, endpoint_used, query_type, duration_ms) "
                "VALUES (%s, %s, %s, %s)",
                (operation, endpoint, query_type, round(duration_ms, 2)),
            )
        conn.commit()
    except Exception:
        pass  # Activity logging must never break application flow


def generate_booking_ref():
    """Generate a short unique booking reference like 'BK-A1B2C3D4'."""
    return "BK-" + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# SQLite schema initialization (local dev mode)
# ---------------------------------------------------------------------------
def init_local_db():
    """Create tables in the local SQLite database and seed data if empty."""
    conn = _get_sqlite_conn()
    cur = conn.cursor()

    # Customers
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            phone         TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Events
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title             TEXT NOT NULL,
            description       TEXT,
            venue             TEXT NOT NULL,
            event_date        TEXT NOT NULL,
            category          TEXT NOT NULL DEFAULT 'General',
            image_url         TEXT,
            total_tickets     INTEGER NOT NULL CHECK (total_tickets >= 0),
            available_tickets INTEGER NOT NULL CHECK (available_tickets >= 0),
            price             REAL NOT NULL CHECK (price >= 0),
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (available_tickets <= total_tickets)
        )
    """)

    # Bookings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id   INTEGER NOT NULL REFERENCES customers (customer_id),
            event_id      INTEGER NOT NULL REFERENCES events (event_id),
            num_tickets   INTEGER NOT NULL CHECK (num_tickets > 0),
            total_price   REAL NOT NULL CHECK (total_price >= 0),
            status        TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
            booking_ref   TEXT NOT NULL UNIQUE,
            booked_at     TEXT NOT NULL DEFAULT (datetime('now')),
            cancelled_at  TEXT
        )
    """)

    # Activity log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS db_activity_log (
            log_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            operation     TEXT NOT NULL,
            endpoint_used TEXT NOT NULL,
            query_type    TEXT,
            duration_ms   REAL,
            recorded_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Seed data if events table is empty
    cur.execute("SELECT COUNT(*) FROM events")
    if cur.fetchone()[0] == 0:
        _seed_local_db(cur)

    conn.commit()
    conn.close()


def _seed_local_db(cur):
    """Insert sample data into the local SQLite database."""
    # Demo customer
    cur.execute(
        "INSERT OR IGNORE INTO customers (full_name, email, phone) VALUES (?, ?, ?)",
        ("Sai Charan", "saicharan@example.com", "+91-9876543210"),
    )

    events = [
        ("Arijit Singh Live in Concert",
         "Experience the magic of Arijit Singh performing his greatest hits live. An unforgettable evening of soulful music under the stars.",
         "Jawaharlal Nehru Stadium, Delhi", "2026-12-15 19:00:00", "Music", None, 5000, 4850, 2500.00),
        ("IPL 2027 — Mumbai Indians vs Chennai Super Kings",
         "The biggest rivalry in IPL returns! Watch MI take on CSK in this blockbuster clash at the Wankhede.",
         "Wankhede Stadium, Mumbai", "2027-03-28 19:30:00", "Sports", None, 33000, 32500, 1500.00),
        ("Stand-Up Comedy Night with Zakir Khan",
         "Get ready for an evening full of laughter with India's favorite comedian. Zakir Khan brings his new show to Bangalore.",
         "Chowdiah Memorial Hall, Bangalore", "2026-11-20 20:00:00", "Comedy", None, 800, 780, 1200.00),
        ("Diljit Dosanjh — Born to Shine Tour",
         "The ultimate Punjabi music extravaganza! Diljit Dosanjh brings his electrifying energy to Hyderabad for one night only.",
         "GMR Arena, Hyderabad", "2027-01-10 18:30:00", "Music", None, 10000, 9800, 3000.00),
        ("Comic Con India 2027",
         "India's biggest pop culture convention is back! Meet your favorite comic artists, cosplay, gaming tournaments and exclusive merchandise.",
         "NESCO Centre, Mumbai", "2027-02-14 10:00:00", "Exhibition", None, 15000, 14500, 800.00),
        ("Bangalore Literature Festival",
         "A celebration of words featuring acclaimed authors, panel discussions, book launches and interactive workshops.",
         "The Lalit Ashok, Bangalore", "2026-12-05 09:00:00", "Conference", None, 2000, 1950, 500.00),
        ("Sunburn Festival Goa 2027",
         "Asia's premier electronic dance music festival returns to Goa with international DJs, stunning stages and three days of non-stop music.",
         "Vagator Beach, Goa", "2027-01-28 16:00:00", "Music", None, 20000, 19500, 4500.00),
        ("India vs Australia — 1st Test",
         "The Border-Gavaskar Trophy continues! Watch India take on Australia in this gripping Test match at the iconic M.A. Chidambaram Stadium.",
         "M.A. Chidambaram Stadium, Chennai", "2027-02-20 09:30:00", "Sports", None, 40000, 39000, 1000.00),
        ("TEDx Chennai 2027",
         "Ideas worth spreading — hear from innovators, artists, scientists and changemakers reshaping India and the world.",
         "IIT Madras, Chennai", "2027-03-15 09:00:00", "Conference", None, 500, 480, 1500.00),
        ("Coldplay — Music of the Spheres World Tour",
         "Coldplay returns to India! Experience the spectacular Music of the Spheres World Tour with dazzling visuals and iconic hits.",
         "DY Patil Stadium, Navi Mumbai", "2027-04-05 18:00:00", "Music", None, 50000, 48000, 6000.00),
    ]
    cur.executemany(
        "INSERT INTO events (title, description, venue, event_date, category, image_url, "
        "total_tickets, available_tickets, price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        events,
    )


# ---------------------------------------------------------------------------
# Routes — Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Home page — list all events."""
    return render_template("index.html")


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    """Event detail page."""
    return render_template("index.html")


@app.route("/bookings")
def bookings_page():
    """Booking history page."""
    return render_template("index.html")


@app.route("/dashboard")
def dashboard_page():
    """Database activity dashboard."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API Routes — Health Check
# ---------------------------------------------------------------------------
@app.route("/api/health")
def api_health():
    """Health check endpoint confirming database mode and service readiness."""
    return jsonify({
        "status": "healthy",
        "mode": "local_sqlite" if USE_LOCAL_DB else "aurora_postgresql",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": "reader",
    })


# ---------------------------------------------------------------------------
# API Routes — Events (READ via reader endpoint)
# ---------------------------------------------------------------------------
@app.route("/api/events")
def api_events():
    """List all events — routed through READER endpoint."""
    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()
            if USE_LOCAL_DB:
                cur.execute(
                    "SELECT event_id, title, description, venue, event_date, category, "
                    "image_url, total_tickets, available_tickets, price FROM events ORDER BY event_date"
                )
                rows = [dict(r) for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT event_id, title, description, venue, event_date, category, "
                    "image_url, total_tickets, available_tickets, price FROM events ORDER BY event_date"
                )
                cols = [desc[0] for desc in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        duration = (time.perf_counter() - start) * 1000
        # Log read activity on writer conn (activity log is a write)
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT events", duration)

        return jsonify({"success": True, "events": rows, "endpoint": "reader", "duration_ms": round(duration, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/events/<int:event_id>")
def api_event_detail(event_id):
    """Get a single event — routed through READER endpoint."""
    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()
            if USE_LOCAL_DB:
                cur.execute(
                    "SELECT event_id, title, description, venue, event_date, category, "
                    "image_url, total_tickets, available_tickets, price FROM events WHERE event_id = ?",
                    (event_id,),
                )
                row = cur.fetchone()
                event = dict(row) if row else None
            else:
                cur.execute(
                    "SELECT event_id, title, description, venue, event_date, category, "
                    "image_url, total_tickets, available_tickets, price FROM events WHERE event_id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
                if row:
                    cols = [desc[0] for desc in cur.description]
                    event = dict(zip(cols, row))
                else:
                    event = None

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT event detail", duration)

        if event is None:
            return jsonify({"success": False, "error": "Event not found"}), 404
        return jsonify({"success": True, "event": event, "endpoint": "reader", "duration_ms": round(duration, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API Routes — Booking (WRITE via writer endpoint)
# ---------------------------------------------------------------------------
@app.route("/api/book", methods=["POST"])
def api_book():
    """
    Book tickets — routed through WRITER endpoint.

    Uses SELECT … FOR UPDATE (PostgreSQL) or immediate transaction (SQLite)
    to prevent overselling when concurrent requests target the same event.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    event_id = data.get("event_id")
    num_tickets = data.get("num_tickets")

    # Validation
    errors = []
    if not name:
        errors.append("Name is required.")
    if not email or "@" not in email:
        errors.append("A valid email is required.")
    if not event_id:
        errors.append("Event ID is required.")
    try:
        num_tickets = int(num_tickets)
        if num_tickets < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Number of tickets must be at least 1.")

    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    start = time.perf_counter()
    try:
        with get_writer_conn() as conn:
            cur = conn.cursor()

            if USE_LOCAL_DB:
                # SQLite: BEGIN IMMEDIATE for write lock
                conn.execute("BEGIN IMMEDIATE")

                # Get or create customer
                cur.execute("SELECT customer_id FROM customers WHERE email = ?", (email,))
                row = cur.fetchone()
                if row:
                    customer_id = row["customer_id"]
                    cur.execute(
                        "UPDATE customers SET full_name = ?, phone = ? WHERE customer_id = ?",
                        (name, phone, customer_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO customers (full_name, email, phone) VALUES (?, ?, ?)",
                        (name, email, phone),
                    )
                    customer_id = cur.lastrowid

                # Lock and check availability
                cur.execute(
                    "SELECT available_tickets, price FROM events WHERE event_id = ?",
                    (event_id,),
                )
                event_row = cur.fetchone()
                if not event_row:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Event not found."}), 404
                if event_row["available_tickets"] < num_tickets:
                    conn.rollback()
                    return jsonify({
                        "success": False,
                        "error": f"Only {event_row['available_tickets']} ticket(s) available."
                    }), 409

                total_price = float(event_row["price"]) * num_tickets
                booking_ref = generate_booking_ref()

                # Atomic inventory decrement
                cur.execute(
                    "UPDATE events SET available_tickets = available_tickets - ? "
                    "WHERE event_id = ? AND available_tickets >= ?",
                    (num_tickets, event_id, num_tickets),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Tickets no longer available."}), 409

                # Create booking
                cur.execute(
                    "INSERT INTO bookings (customer_id, event_id, num_tickets, total_price, booking_ref) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (customer_id, event_id, num_tickets, total_price, booking_ref),
                )
            else:
                # PostgreSQL: Use SELECT … FOR UPDATE for row-level locking
                import psycopg2

                # Get or create customer
                cur.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
                row = cur.fetchone()
                if row:
                    customer_id = row[0]
                    cur.execute(
                        "UPDATE customers SET full_name = %s, phone = %s WHERE customer_id = %s",
                        (name, phone, customer_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO customers (full_name, email, phone) VALUES (%s, %s, %s) RETURNING customer_id",
                        (name, email, phone),
                    )
                    customer_id = cur.fetchone()[0]

                # Lock the event row and check availability
                cur.execute(
                    "SELECT available_tickets, price FROM events WHERE event_id = %s FOR UPDATE",
                    (event_id,),
                )
                event_row = cur.fetchone()
                if not event_row:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Event not found."}), 404
                if event_row[0] < num_tickets:
                    conn.rollback()
                    return jsonify({
                        "success": False,
                        "error": f"Only {event_row[0]} ticket(s) available."
                    }), 409

                total_price = float(event_row[1]) * num_tickets
                booking_ref = generate_booking_ref()

                # Atomic inventory decrement
                cur.execute(
                    "UPDATE events SET available_tickets = available_tickets - %s "
                    "WHERE event_id = %s AND available_tickets >= %s",
                    (num_tickets, event_id, num_tickets),
                )
                if cur.rowcount == 0:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Tickets no longer available."}), 409

                # Create booking
                cur.execute(
                    "INSERT INTO bookings (customer_id, event_id, num_tickets, total_price, booking_ref) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (customer_id, event_id, num_tickets, total_price, booking_ref),
                )

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "WRITE", "writer", "INSERT booking", duration)

        return jsonify({
            "success": True,
            "booking_ref": booking_ref,
            "num_tickets": num_tickets,
            "total_price": total_price,
            "endpoint": "writer",
            "duration_ms": round(duration, 2),
        }), 201

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    """
    Cancel a booking — routed through WRITER endpoint.

    Prevents double-cancellation by checking the current status before updating.
    Restores inventory atomically.
    """
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    booking_ref = (data.get("booking_ref") or "").strip()
    if not booking_ref:
        return jsonify({"success": False, "error": "Booking reference is required."}), 400

    start = time.perf_counter()
    try:
        with get_writer_conn() as conn:
            cur = conn.cursor()

            if USE_LOCAL_DB:
                conn.execute("BEGIN IMMEDIATE")

                cur.execute(
                    "SELECT booking_id, event_id, num_tickets, status FROM bookings WHERE booking_ref = ?",
                    (booking_ref,),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Booking not found."}), 404
                if row["status"] == "cancelled":
                    conn.rollback()
                    return jsonify({"success": False, "error": "Booking is already cancelled."}), 409

                # Restore inventory
                cur.execute(
                    "UPDATE events SET available_tickets = available_tickets + ? WHERE event_id = ?",
                    (row["num_tickets"], row["event_id"]),
                )

                # Mark cancelled
                cur.execute(
                    "UPDATE bookings SET status = 'cancelled', cancelled_at = datetime('now') "
                    "WHERE booking_id = ?",
                    (row["booking_id"],),
                )
            else:
                # PostgreSQL: lock the booking row
                cur.execute(
                    "SELECT booking_id, event_id, num_tickets, status FROM bookings "
                    "WHERE booking_ref = %s FOR UPDATE",
                    (booking_ref,),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return jsonify({"success": False, "error": "Booking not found."}), 404
                if row[3] == "cancelled":
                    conn.rollback()
                    return jsonify({"success": False, "error": "Booking is already cancelled."}), 409

                booking_id, event_id, num_tickets = row[0], row[1], row[2]

                # Lock event row and restore inventory
                cur.execute(
                    "UPDATE events SET available_tickets = available_tickets + %s WHERE event_id = %s",
                    (num_tickets, event_id),
                )

                cur.execute(
                    "UPDATE bookings SET status = 'cancelled', cancelled_at = NOW() AT TIME ZONE 'UTC' "
                    "WHERE booking_id = %s",
                    (booking_id,),
                )

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "WRITE", "writer", "UPDATE cancel booking", duration)

        return jsonify({
            "success": True,
            "message": "Booking cancelled successfully.",
            "booking_ref": booking_ref,
            "endpoint": "writer",
            "duration_ms": round(duration, 2),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API Routes — Booking History (READ via reader endpoint)
# ---------------------------------------------------------------------------
@app.route("/api/bookings")
def api_bookings():
    """List bookings for an email — routed through READER endpoint."""
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "error": "Email parameter is required."}), 400

    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()
            if USE_LOCAL_DB:
                cur.execute(
                    "SELECT b.booking_id, b.booking_ref, b.num_tickets, b.total_price, "
                    "b.status, b.booked_at, b.cancelled_at, "
                    "e.title AS event_title, e.venue, e.event_date "
                    "FROM bookings b JOIN events e ON b.event_id = e.event_id "
                    "JOIN customers c ON b.customer_id = c.customer_id "
                    "WHERE c.email = ? ORDER BY b.booked_at DESC",
                    (email,),
                )
                rows = [dict(r) for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT b.booking_id, b.booking_ref, b.num_tickets, b.total_price, "
                    "b.status, b.booked_at, b.cancelled_at, "
                    "e.title AS event_title, e.venue, e.event_date "
                    "FROM bookings b JOIN events e ON b.event_id = e.event_id "
                    "JOIN customers c ON b.customer_id = c.customer_id "
                    "WHERE c.email = %s ORDER BY b.booked_at DESC",
                    (email,),
                )
                cols = [desc[0] for desc in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT bookings", duration)

        return jsonify({"success": True, "bookings": rows, "endpoint": "reader", "duration_ms": round(duration, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API Routes — Dashboard (READ via reader endpoint)
# ---------------------------------------------------------------------------
@app.route("/api/dashboard/stats")
@app.route("/api/stats")
def api_dashboard_stats():
    """Dashboard statistics — routed through READER endpoint."""
    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()

            if USE_LOCAL_DB:
                cur.execute("SELECT COUNT(*) FROM events")
                total_events = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM bookings WHERE status = 'confirmed'")
                total_bookings = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(num_tickets), 0) FROM bookings WHERE status = 'confirmed'")
                total_tickets_sold = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(total_price), 0) FROM bookings WHERE status = 'confirmed'")
                total_revenue = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM customers")
                total_customers = cur.fetchone()[0]
            else:
                cur.execute("SELECT COUNT(*) FROM events")
                total_events = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM bookings WHERE status = 'confirmed'")
                total_bookings = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(num_tickets), 0) FROM bookings WHERE status = 'confirmed'")
                total_tickets_sold = cur.fetchone()[0]
                cur.execute("SELECT COALESCE(SUM(total_price), 0) FROM bookings WHERE status = 'confirmed'")
                total_revenue = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM customers")
                total_customers = cur.fetchone()[0]

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT dashboard stats", duration)

        return jsonify({
            "success": True,
            "stats": {
                "total_events": total_events,
                "total_bookings": total_bookings,
                "total_tickets_sold": int(total_tickets_sold),
                "total_revenue": float(total_revenue),
                "total_customers": total_customers,
            },
            "endpoint": "reader",
            "duration_ms": round(duration, 2),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/activity")
def api_dashboard_activity():
    """Recent database activity — routed through READER endpoint."""
    limit = request.args.get("limit", 50, type=int)
    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()
            if USE_LOCAL_DB:
                cur.execute(
                    "SELECT log_id, operation, endpoint_used, query_type, duration_ms, recorded_at "
                    "FROM db_activity_log ORDER BY recorded_at DESC LIMIT ?",
                    (limit,),
                )
                rows = [dict(r) for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT log_id, operation, endpoint_used, query_type, duration_ms, recorded_at "
                    "FROM db_activity_log ORDER BY recorded_at DESC LIMIT %s",
                    (limit,),
                )
                cols = [desc[0] for desc in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT activity log", duration)

        return jsonify({"success": True, "activity": rows, "endpoint": "reader", "duration_ms": round(duration, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dashboard/endpoint-summary")
def api_dashboard_endpoint_summary():
    """Aggregate counts by endpoint — routed through READER endpoint."""
    start = time.perf_counter()
    try:
        with get_reader_conn() as conn:
            cur = conn.cursor()
            if USE_LOCAL_DB:
                cur.execute(
                    "SELECT endpoint_used, operation, COUNT(*) as count, "
                    "ROUND(AVG(duration_ms), 2) as avg_duration_ms "
                    "FROM db_activity_log GROUP BY endpoint_used, operation"
                )
                rows = [dict(r) for r in cur.fetchall()]
            else:
                cur.execute(
                    "SELECT endpoint_used, operation, COUNT(*) as count, "
                    "ROUND(AVG(duration_ms)::numeric, 2) as avg_duration_ms "
                    "FROM db_activity_log GROUP BY endpoint_used, operation"
                )
                cols = [desc[0] for desc in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        duration = (time.perf_counter() - start) * 1000
        with get_writer_conn() as wconn:
            log_activity(wconn, "READ", "reader", "SELECT endpoint summary", duration)

        return jsonify({"success": True, "summary": rows, "endpoint": "reader", "duration_ms": round(duration, 2)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/config")
def api_config():
    """Return non-secret configuration info for the dashboard."""
    return jsonify({
        "success": True,
        "config": {
            "use_local_db": USE_LOCAL_DB,
            "writer_host": AURORA_WRITER_HOST[:20] + "..." if len(AURORA_WRITER_HOST) > 20 else AURORA_WRITER_HOST or "(local)",
            "reader_host": AURORA_READER_HOST[:20] + "..." if len(AURORA_READER_HOST) > 20 else AURORA_READER_HOST or "(local)",
            "db_name": AURORA_DB_NAME if not USE_LOCAL_DB else "local_ticket_booking.db",
        },
    })


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
if USE_LOCAL_DB:
    init_local_db()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=5000)
