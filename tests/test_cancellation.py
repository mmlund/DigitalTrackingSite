"""
Tests for Phase 3B: Appointment Cancellations Tracking

Covers:
  - Dedupe key computation
  - Late vs early cancellation classification
  - Cancellation enrichment (fields + validation)
  - Appointment field promotion in track_handler
  - Appointment_id normalization from transaction_id
  - Dedupe prevention at ingestion
  - Report service appointment-linked funnel metrics
"""

import unittest
import hashlib
from datetime import datetime, timedelta, timezone

from app import create_app
from src.cancellation_service import (
    compute_dedupe_key,
    classify_cancellation,
    enrich_cancellation_event,
    LATE_CANCEL_THRESHOLD_HOURS,
)
from src.database import get_collection


class TestDedupeKey(unittest.TestCase):
    """Test dedupe key computation."""

    def test_same_inputs_same_key(self):
        t = datetime(2025, 3, 1, 10, 0)
        k1 = compute_dedupe_key("ea", "scandinavian", "EA-42", t)
        k2 = compute_dedupe_key("ea", "scandinavian", "EA-42", t)
        self.assertEqual(k1, k2)

    def test_stable_across_retries_on_same_day(self):
        """Timestamp variation within same day results in same key."""
        t1 = "2025-03-01T10:00:00Z"
        t2 = "2025-03-01T14:30:00Z"
        k1 = compute_dedupe_key("ea", "scandinavian", "EA-42", t1)
        k2 = compute_dedupe_key("ea", "scandinavian", "EA-42", t2)
        self.assertEqual(k1, k2, "Keys should be identical for the same day")

    def test_different_day_different_key(self):
        k1 = compute_dedupe_key("ea", "scand", "EA-1", "2025-03-01T10:00:00")
        k2 = compute_dedupe_key("ea", "scand", "EA-1", "2025-03-02T10:00:00")
        self.assertNotEqual(k1, k2)

    def test_no_appointment_id_returns_none(self):
        self.assertIsNone(compute_dedupe_key("ea", "s", None, datetime.utcnow()))

class TestClassification(unittest.TestCase):
    """Test late vs early cancellation classification."""

    def test_late_cancel_utc_normalization(self):
        """Test with explicit timezone offsets."""
        # Appt at 10:00 UTC
        appt = datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc)
        # Cancel at 11:00 UTC-5 (06:00 local) -> 16:00 UTC (Too late)
        cancel = datetime(2025, 3, 1, 11, 0, tzinfo=timezone(timedelta(hours=-5)))
        
        cls, hours = classify_cancellation(appt, cancel)
        self.assertEqual(cls, "late_cancel")
        self.assertEqual(hours, -6.0) # 10:00 - 16:00 = -6

    def test_early_cancel_utc_normalization(self):
        # Appt at 10:00 UTC
        appt = datetime(2025, 3, 5, 10, 0, tzinfo=timezone.utc)
        # Cancel 4 days before
        cancel = datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc)
        cls, hours = classify_cancellation(appt, cancel)
        self.assertEqual(cls, "early_cancel")
        self.assertEqual(hours, 96.0)

    def test_string_datetimes_with_z(self):
        cls, hours = classify_cancellation(
            "2025-03-01T10:00:00Z", "2025-03-01T08:00:00Z"
        )
        self.assertEqual(cls, "late_cancel")
        self.assertAlmostEqual(hours, 2.0)

    def test_missing_values(self):
        cls, hours = classify_cancellation(None, datetime.utcnow())
        self.assertEqual(cls, "unknown")
        self.assertIsNone(hours)


class TestEnrichment(unittest.TestCase):
    """Test cancellation event enrichment."""

    def test_enrichment_attaches_fields(self):
        event = {
            "event_type": "booking_cancelled",
            "appointment_id": "EA-42",
            "appointment_datetime": "2025-03-05T10:00:00",
            "occurred_at": datetime(2025, 3, 1, 10, 0),
            "source_system": "easyappointments_scandinavian",
            "cancelled_by": "patient",
        }
        enrich_cancellation_event(event)
        self.assertIn("dedupe_key", event)
        self.assertEqual(event["cancel_classification"], "early_cancel")
        self.assertIn("lead_time_hours", event)
        self.assertEqual(event["cancelled_by"], "patient")

    def test_cancelled_by_validation(self):
        """Invalid cancelled_by defaults to unknown."""
        event = {
            "event_type": "booking_cancelled",
            "appointment_id": "EA-1",
            "cancelled_by": "receptionist",
            "occurred_at": datetime.utcnow(),
            "source_system": "ea",
        }
        enrich_cancellation_event(event)
        self.assertEqual(event["cancelled_by"], "unknown")

    def test_cancelled_by_missing(self):
        event = {
            "event_type": "booking_cancelled",
            "appointment_id": "EA-1",
            "occurred_at": datetime.utcnow(),
            "source_system": "ea",
        }
        enrich_cancellation_event(event)
        self.assertEqual(event["cancelled_by"], "unknown")

    def test_cancelled_by_case_insensitive(self):
        event = {
            "event_type": "booking_cancelled",
            "appointment_id": "EA-1",
            "cancelled_by": "ADMIN",
            "occurred_at": datetime.utcnow(),
            "source_system": "ea",
        }
        enrich_cancellation_event(event)
        self.assertEqual(event["cancelled_by"], "admin")


class TestAppointmentFieldPromotion(unittest.TestCase):
    """Test that appointment fields are promoted by track_handler."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        get_collection("raw_events").delete_many({})

    def tearDown(self):
        get_collection("raw_events").delete_many({})
        self.ctx.pop()

    def test_appointment_id_promoted(self):
        resp = self.client.post("/track", json={
            "event_type": "booking_confirmed",
            "appointment_id": "EA-42",
            "appointment_datetime": "2025-03-01T10:00:00",
            "customer_email": "test@example.com",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)
        events = list(get_collection("raw_events").find(
            {"event_type": "booking_confirmed"}
        ))
        self.assertGreaterEqual(len(events), 1)
        ev = events[-1]
        self.assertEqual(ev.get("appointment_id"), "EA-42")
        self.assertEqual(ev.get("appointment_datetime"), "2025-03-01T10:00:00")

    def test_appointment_id_from_transaction_id(self):
        """purchase with transaction_id=EA-X → appointment_id normalized."""
        resp = self.client.post("/track", json={
            "event_type": "purchase",
            "transaction_id": "EA-99",
            "revenue": "100",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)
        events = list(get_collection("raw_events").find(
            {"event_type": "purchase"}
        ))
        ev = events[-1]
        self.assertEqual(ev.get("appointment_id"), "EA-99")

    def test_appointment_id_from_booking_id(self):
        """booking_confirmed with booking_id → appointment_id."""
        resp = self.client.post("/track", json={
            "event_type": "booking_confirmed",
            "booking_id": "42",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)
        events = list(get_collection("raw_events").find(
            {"event_type": "booking_confirmed"}
        ))
        ev = events[-1]
        self.assertEqual(ev.get("appointment_id"), "42")


class TestCancellationDedupe(unittest.TestCase):
    """Test that duplicate booking_cancelled events are deduplicated."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        get_collection("raw_events").delete_many({})
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})

    def tearDown(self):
        get_collection("raw_events").delete_many({})
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        self.ctx.pop()

    def test_duplicate_cancellation_skipped(self):
        """Same booking_cancelled sent twice → only one stored."""
        payload = {
            "event_type": "booking_cancelled",
            "appointment_id": "EA-42",
            "appointment_datetime": "2025-03-01T10:00:00",
            "cancelled_by": "patient",
            "customer_email": "cancel@test.com",
            "source_system": "easyappointments_scandinavian",
            "site_id": "scandinavian",
            "timestamp": "2025-02-28T10:00:00",
        }
        resp1 = self.client.post("/track", json=payload)
        self.assertEqual(resp1.status_code, 200)

        resp2 = self.client.post("/track", json=payload)
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertEqual(data2.get("dedupe"), "skipped")

        events = list(get_collection("raw_events").find(
            {"event_type": "booking_cancelled"}
        ))
        self.assertEqual(len(events), 1)


class TestCancellationEnrichmentE2E(unittest.TestCase):
    """End-to-end: booking_cancelled via /track gets classification fields."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        get_collection("raw_events").delete_many({})
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})

    def tearDown(self):
        get_collection("raw_events").delete_many({})
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        self.ctx.pop()

    def test_cancellation_has_classification(self):
        resp = self.client.post("/track", json={
            "event_type": "booking_cancelled",
            "appointment_id": "EA-55",
            "appointment_datetime": "2025-03-05T10:00:00",
            "cancelled_by": "patient",
            "cancel_reason": "Schedule conflict",
            "customer_email": "cancel2@test.com",
            "source_system": "easyappointments_scandinavian",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)

        events = list(get_collection("raw_events").find(
            {"event_type": "booking_cancelled"}
        ))
        ev = events[-1]
        self.assertIn("cancel_classification", ev)
        self.assertIn("dedupe_key", ev)
        self.assertEqual(ev["cancelled_by"], "patient")
        self.assertEqual(ev["cancel_reason"], "Schedule conflict")
        # PII should be stripped (booking_cancelled is identity-eligible)
        self.assertNotIn("customer_email", ev)
        # But person_id should be present
        self.assertIn("person_id", ev)


if __name__ == "__main__":
    unittest.main()
