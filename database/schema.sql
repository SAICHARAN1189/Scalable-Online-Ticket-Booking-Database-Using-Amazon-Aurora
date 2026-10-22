-- ============================================================
-- Aurora Ticket Booking — PostgreSQL Schema
-- ============================================================
-- Designed for Amazon Aurora PostgreSQL.
-- All timestamps are UTC.  Booking logic uses row-level locks
-- (SELECT … FOR UPDATE) to prevent overselling.
-- ============================================================

-- Grant rds_iam role to master user for IAM Database Authentication
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rds_iam') THEN
        EXECUTE 'GRANT rds_iam TO postgres';
    END IF;
END $$;

-- 1. Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id     SERIAL PRIMARY KEY,
    full_name       VARCHAR(200)  NOT NULL,
    email           VARCHAR(254)  NOT NULL UNIQUE,
    phone           VARCHAR(20),
    created_at      TIMESTAMP     NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX idx_customers_email ON customers (email);

-- 2. Events
CREATE TABLE IF NOT EXISTS events (
    event_id        SERIAL PRIMARY KEY,
    title           VARCHAR(300)  NOT NULL,
    description     TEXT,
    venue           VARCHAR(300)  NOT NULL,
    event_date      TIMESTAMP     NOT NULL,
    category        VARCHAR(100)  NOT NULL DEFAULT 'General',
    image_url       VARCHAR(500),
    total_tickets   INTEGER       NOT NULL CHECK (total_tickets >= 0),
    available_tickets INTEGER     NOT NULL CHECK (available_tickets >= 0),
    price           NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    created_at      TIMESTAMP     NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    CONSTRAINT chk_available_le_total
        CHECK (available_tickets <= total_tickets)
);

CREATE INDEX idx_events_date     ON events (event_date);
CREATE INDEX idx_events_category ON events (category);

-- 3. Bookings
CREATE TABLE IF NOT EXISTS bookings (
    booking_id      SERIAL PRIMARY KEY,
    customer_id     INTEGER       NOT NULL REFERENCES customers (customer_id),
    event_id        INTEGER       NOT NULL REFERENCES events (event_id),
    num_tickets     INTEGER       NOT NULL CHECK (num_tickets > 0),
    total_price     NUMERIC(10,2) NOT NULL CHECK (total_price >= 0),
    status          VARCHAR(20)   NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
    booking_ref     VARCHAR(20)   NOT NULL UNIQUE,
    booked_at       TIMESTAMP     NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    cancelled_at    TIMESTAMP
);

CREATE INDEX idx_bookings_customer ON bookings (customer_id);
CREATE INDEX idx_bookings_event    ON bookings (event_id);
CREATE INDEX idx_bookings_ref      ON bookings (booking_ref);
CREATE INDEX idx_bookings_status   ON bookings (status);

-- 4. Database activity log (for the dashboard)
CREATE TABLE IF NOT EXISTS db_activity_log (
    log_id          SERIAL PRIMARY KEY,
    operation       VARCHAR(20)   NOT NULL,   -- 'READ' or 'WRITE'
    endpoint_used   VARCHAR(10)   NOT NULL,   -- 'writer' or 'reader'
    query_type      VARCHAR(50),              -- e.g. 'SELECT events', 'INSERT booking'
    duration_ms     NUMERIC(10,2),
    recorded_at     TIMESTAMP     NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

CREATE INDEX idx_activity_recorded ON db_activity_log (recorded_at);
