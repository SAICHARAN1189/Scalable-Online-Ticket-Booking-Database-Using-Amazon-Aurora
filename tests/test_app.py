"""
Aurora Ticket Booking — Unit & Integration Tests
=================================================
Tests run against the local SQLite database.
They verify booking logic, cancellation, overselling prevention,
and API endpoint correctness.
"""

import os
import sys
import json
import unittest
import threading
import time

# Ensure we use local DB for tests
os.environ["USE_LOCAL_DB"] = "true"
os.environ["FLASK_SECRET_KEY"] = "test-secret-key"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_local_db, LOCAL_DB_PATH


class BaseTestCase(unittest.TestCase):
    """Base class that resets the database before each test."""

    def setUp(self):
        """Create a fresh database for each test."""
        # Remove existing DB
        if os.path.exists(LOCAL_DB_PATH):
            os.remove(LOCAL_DB_PATH)
        # Re-initialize
        init_local_db()
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(LOCAL_DB_PATH):
            os.remove(LOCAL_DB_PATH)


class TestEventsAPI(BaseTestCase):
    """Test event listing and detail endpoints."""

    def test_list_events(self):
        """GET /api/events should return all seeded events."""
        res = self.client.get("/api/events")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["events"]), 10)
        self.assertEqual(data["endpoint"], "reader")

    def test_event_detail(self):
        """GET /api/events/1 should return a single event."""
        res = self.client.get("/api/events/1")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertIn("event", data)
        self.assertEqual(data["event"]["event_id"], 1)

    def test_event_not_found(self):
        """GET /api/events/999 should return 404."""
        res = self.client.get("/api/events/999")
        data = res.get_json()
        self.assertEqual(res.status_code, 404)
        self.assertFalse(data["success"])

    def test_events_have_required_fields(self):
        """Each event must have all expected fields."""
        res = self.client.get("/api/events")
        data = res.get_json()
        required = {"event_id", "title", "description", "venue", "event_date",
                     "category", "total_tickets", "available_tickets", "price"}
        for event in data["events"]:
            self.assertTrue(required.issubset(event.keys()),
                            f"Missing fields: {required - event.keys()}")


class TestBookingAPI(BaseTestCase):
    """Test booking creation."""

    def _book(self, event_id=1, name="Test User", email="test@example.com",
              phone="+91-1234567890", num_tickets=2):
        return self.client.post("/api/book", json={
            "event_id": event_id,
            "name": name,
            "email": email,
            "phone": phone,
            "num_tickets": num_tickets,
        })

    def test_successful_booking(self):
        """A valid booking should return 201 with a booking reference."""
        res = self._book()
        data = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertTrue(data["success"])
        self.assertIn("booking_ref", data)
        self.assertTrue(data["booking_ref"].startswith("BK-"))
        self.assertEqual(data["num_tickets"], 2)
        self.assertEqual(data["endpoint"], "writer")

    def test_booking_decrements_inventory(self):
        """After booking, available_tickets should decrease."""
        # Get initial availability
        res1 = self.client.get("/api/events/1")
        initial = res1.get_json()["event"]["available_tickets"]

        self._book(num_tickets=3)

        res2 = self.client.get("/api/events/1")
        after = res2.get_json()["event"]["available_tickets"]
        self.assertEqual(after, initial - 3)

    def test_booking_validation_missing_name(self):
        """Booking without a name should fail."""
        res = self._book(name="")
        data = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertFalse(data["success"])

    def test_booking_validation_bad_email(self):
        """Booking with an invalid email should fail."""
        res = self._book(email="not-an-email")
        data = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertFalse(data["success"])

    def test_booking_validation_zero_tickets(self):
        """Booking 0 tickets should fail."""
        res = self._book(num_tickets=0)
        data = res.get_json()
        self.assertEqual(res.status_code, 400)
        self.assertFalse(data["success"])

    def test_booking_nonexistent_event(self):
        """Booking for a non-existent event should fail."""
        res = self._book(event_id=999)
        data = res.get_json()
        self.assertEqual(res.status_code, 404)
        self.assertFalse(data["success"])

    def test_booking_insufficient_tickets(self):
        """Booking more tickets than available should fail."""
        res = self._book(num_tickets=100000)
        data = res.get_json()
        self.assertIn(res.status_code, [409, 400])
        self.assertFalse(data["success"])


class TestCancellationAPI(BaseTestCase):
    """Test booking cancellation."""

    def _book_and_get_ref(self):
        res = self.client.post("/api/book", json={
            "event_id": 1, "name": "Cancel Test",
            "email": "cancel@test.com", "num_tickets": 2,
        })
        return res.get_json()["booking_ref"]

    def test_successful_cancellation(self):
        """Cancelling a confirmed booking should succeed."""
        ref = self._book_and_get_ref()
        res = self.client.post("/api/cancel", json={"booking_ref": ref})
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["endpoint"], "writer")

    def test_cancellation_restores_inventory(self):
        """Cancellation must restore available_tickets."""
        initial = self.client.get("/api/events/1").get_json()["event"]["available_tickets"]
        ref = self._book_and_get_ref()
        after_book = self.client.get("/api/events/1").get_json()["event"]["available_tickets"]
        self.assertEqual(after_book, initial - 2)

        self.client.post("/api/cancel", json={"booking_ref": ref})
        after_cancel = self.client.get("/api/events/1").get_json()["event"]["available_tickets"]
        self.assertEqual(after_cancel, initial)

    def test_double_cancellation_prevented(self):
        """Cancelling the same booking twice should fail."""
        ref = self._book_and_get_ref()
        self.client.post("/api/cancel", json={"booking_ref": ref})
        res = self.client.post("/api/cancel", json={"booking_ref": ref})
        data = res.get_json()
        self.assertEqual(res.status_code, 409)
        self.assertFalse(data["success"])
        self.assertIn("already cancelled", data["error"].lower())

    def test_cancel_nonexistent_booking(self):
        """Cancelling a non-existent booking should return 404."""
        res = self.client.post("/api/cancel", json={"booking_ref": "BK-NONEXIST"})
        data = res.get_json()
        self.assertEqual(res.status_code, 404)
        self.assertFalse(data["success"])


class TestBookingHistory(BaseTestCase):
    """Test booking history retrieval."""

    def test_booking_history(self):
        """Bookings should appear in history for the customer's email."""
        self.client.post("/api/book", json={
            "event_id": 1, "name": "History Test",
            "email": "history@test.com", "num_tickets": 1,
        })
        res = self.client.get("/api/bookings?email=history@test.com")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["bookings"]), 1)
        self.assertEqual(data["endpoint"], "reader")

    def test_empty_history(self):
        """Unknown email should return empty list."""
        res = self.client.get("/api/bookings?email=nobody@test.com")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["bookings"]), 0)


class TestDashboardAPI(BaseTestCase):
    """Test dashboard endpoints."""

    def test_dashboard_stats(self):
        """Dashboard stats should return expected fields."""
        res = self.client.get("/api/dashboard/stats")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        stats = data["stats"]
        self.assertIn("total_events", stats)
        self.assertIn("total_bookings", stats)
        self.assertIn("total_tickets_sold", stats)
        self.assertIn("total_revenue", stats)
        self.assertEqual(stats["total_events"], 10)

    def test_config_endpoint(self):
        """Config should indicate local DB mode."""
        res = self.client.get("/api/config")
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["use_local_db"])


class TestConcurrentBooking(BaseTestCase):
    """
    Test that concurrent bookings cannot oversell inventory.
    Uses threading to simulate parallel booking attempts.
    """

    def test_no_overselling(self):
        """
        Create an event with exactly 5 tickets.
        Launch 20 threads each trying to book 1 ticket.
        At most 5 should succeed.
        """
        import sqlite3
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.execute("PRAGMA foreign_keys=ON")
        # Create a limited event
        conn.execute(
            "INSERT INTO events (title, description, venue, event_date, category, "
            "total_tickets, available_tickets, price) "
            "VALUES ('Concurrency Test Event', 'Test', 'Test Venue', "
            "'2027-06-01 10:00:00', 'General', 5, 5, 100.00)"
        )
        conn.commit()
        # Find the event_id
        cur = conn.execute("SELECT event_id FROM events WHERE title='Concurrency Test Event'")
        event_id = cur.fetchone()[0]
        conn.close()

        results = []
        def attempt_booking(i):
            with self.app.test_client() as c:
                res = c.post("/api/book", json={
                    "event_id": event_id,
                    "name": f"User {i}",
                    "email": f"user{i}@concurrent.test",
                    "num_tickets": 1,
                })
                results.append(res.get_json())

        threads = [threading.Thread(target=attempt_booking, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        successful = sum(1 for r in results if r.get("success"))
        self.assertLessEqual(successful, 5,
                             f"Oversold! {successful} bookings succeeded for 5 tickets")
        self.assertGreater(successful, 0, "At least one booking should succeed")

        # Verify final inventory
        res = self.client.get(f"/api/events/{event_id}")
        remaining = res.get_json()["event"]["available_tickets"]
        self.assertEqual(remaining, 5 - successful,
                         f"Inventory mismatch: {remaining} remaining after {successful} bookings")


class TestPageRoutes(BaseTestCase):
    """Test that HTML page routes return 200."""

    def test_home_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)

    def test_bookings_page(self):
        res = self.client.get("/bookings")
        self.assertEqual(res.status_code, 200)

    def test_dashboard_page(self):
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)


class TestHealthAndMonitoringAPI(BaseTestCase):
    """Test health check and telemetry monitoring endpoints."""

    def test_health_check(self):
        """GET /api/health returns 200 with healthy status and mode."""
        res = self.client.get("/api/health")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["mode"], "local_sqlite")
        self.assertEqual(data["endpoint"], "reader")

    def test_stats_alias_endpoint(self):
        """GET /api/stats returns 200 and matches /api/dashboard/stats structure."""
        res = self.client.get("/api/stats")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertIn("stats", data)
        self.assertIn("total_events", data["stats"])

    def test_config_endpoint(self):
        """GET /api/config returns non-secret runtime config."""
        res = self.client.get("/api/config")
        data = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data["success"])
        self.assertTrue(data["config"]["use_local_db"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
