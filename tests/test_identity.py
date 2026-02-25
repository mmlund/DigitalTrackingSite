"""
Tests for Phase 3A: Patient Identity Handling

Covers:
  - Hash normalization (email, phone, both, none)
  - Identity resolution (create, return existing, update last_seen)
  - PII stripping (top-level + raw_params)
  - End-to-end ingestion via /track endpoint
  - Repeat patient detection
"""

import unittest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app
from src.identity_service import (
    compute_customer_key_hash,
    resolve_person_id,
    strip_pii_from_event,
    process_identity,
    _normalize_email,
    _normalize_phone,
    IDENTITY_EVENT_TYPES,
    PII_FIELDS,
)
from src.database import get_collection


class TestHashing(unittest.TestCase):
    """Test customer_key_hash computation and normalization."""

    def test_hash_email_normalization(self):
        """Different capitalizations/whitespace → same hash."""
        h1, s1 = compute_customer_key_hash(email="Test@Example.COM")
        h2, s2 = compute_customer_key_hash(email="  test@example.com  ")
        self.assertEqual(h1, h2)
        self.assertEqual(s1, "email")

    def test_hash_phone_normalization(self):
        """Parentheses/dashes stripped, +1 prepended for 10-digit."""
        h1, _ = compute_customer_key_hash(phone="(555) 123-4567")
        h2, _ = compute_customer_key_hash(phone="+15551234567")
        self.assertEqual(h1, h2)

    def test_hash_email_preferred_over_phone(self):
        """When both present, hash comes from email, source='both'."""
        h_both, src = compute_customer_key_hash(
            email="a@b.com", phone="+15551234567"
        )
        h_email, _ = compute_customer_key_hash(email="a@b.com")
        self.assertEqual(h_both, h_email)
        self.assertEqual(src, "both")

    def test_hash_no_input(self):
        """No email, no phone → (None, 'unknown')."""
        h, src = compute_customer_key_hash()
        self.assertIsNone(h)
        self.assertEqual(src, "unknown")

    def test_hash_invalid_email(self):
        """String without @ → treated as no email."""
        h, src = compute_customer_key_hash(email="notanemail")
        self.assertIsNone(h)
        self.assertEqual(src, "unknown")

    def test_hash_short_phone(self):
        """Phone with < 7 digits → treated as no phone."""
        h, src = compute_customer_key_hash(phone="123")
        self.assertIsNone(h)
        self.assertEqual(src, "unknown")

    def test_hash_deterministic(self):
        """Same input always → same hash."""
        h1, _ = compute_customer_key_hash(email="stable@test.com")
        h2, _ = compute_customer_key_hash(email="stable@test.com")
        self.assertEqual(h1, h2)
        # Verify it's actually SHA-256
        expected = hashlib.sha256("email:stable@test.com".encode()).hexdigest()
        self.assertEqual(h1, expected)

    def test_hash_phone_only(self):
        """Phone-only → source = 'phone'."""
        h, src = compute_customer_key_hash(phone="+4412345678901")
        self.assertIsNotNone(h)
        self.assertEqual(src, "phone")


class TestIdentityResolution(unittest.TestCase):
    """Test resolve_person_id with mock collections."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.ctx = self.app.app_context()
        self.ctx.push()
        # Clean identity collections
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})

    def tearDown(self):
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        self.ctx.pop()

    def test_resolve_creates_new_person(self):
        """First seen hash → new identity + person_id."""
        h, _ = compute_customer_key_hash(email="new@patient.com")
        pid = resolve_person_id(h, datetime.utcnow(), "scandinavian", "booking_confirmed")
        self.assertIsNotNone(pid)
        # Identity doc exists
        doc = get_collection("identities").find_one({"person_id": pid})
        self.assertIsNotNone(doc)
        self.assertIn(h, doc["customer_keys"])

    def test_resolve_returns_existing_person(self):
        """Same hash → same person_id."""
        h, _ = compute_customer_key_hash(email="repeat@patient.com")
        pid1 = resolve_person_id(h, datetime.utcnow(), "scandinavian", "booking_confirmed")
        pid2 = resolve_person_id(h, datetime.utcnow(), "scandinavian", "attended")
        self.assertEqual(pid1, pid2)

    def test_resolve_updates_last_seen(self):
        """Second resolution updates last_seen_at."""
        h, _ = compute_customer_key_hash(email="seen@twice.com")
        t1 = datetime(2025, 1, 1)
        t2 = datetime(2025, 6, 1)
        resolve_person_id(h, t1, "scandinavian", "booking_confirmed")
        resolve_person_id(h, t2, "scandinavian", "attended")
        doc = get_collection("identities").find_one({"customer_keys": h})
        self.assertEqual(doc["last_seen_at"], t2)

    def test_identity_link_created(self):
        """Each resolution creates an audit link."""
        h, _ = compute_customer_key_hash(email="audit@trail.com")
        resolve_person_id(h, datetime.utcnow(), "scandinavian", "booking_confirmed")
        resolve_person_id(h, datetime.utcnow(), "scandinavian", "attended")
        links = list(get_collection("identity_links").find({"customer_key_hash": h}))
        self.assertEqual(len(links), 2)
        event_types = {l["seen_in_event_type"] for l in links}
        self.assertIn("booking_confirmed", event_types)
        self.assertIn("attended", event_types)

    def test_resolve_null_hash(self):
        """None hash → returns None."""
        pid = resolve_person_id(None, datetime.utcnow())
        self.assertIsNone(pid)

    def test_resolve_adds_source_system(self):
        """source_system is added to identity doc."""
        h, _ = compute_customer_key_hash(email="source@test.com")
        resolve_person_id(h, datetime.utcnow(), source_system="easyappointments_scandinavian")
        doc = get_collection("identities").find_one({"customer_keys": h})
        self.assertIn("easyappointments_scandinavian", doc["source_systems"])


class TestPIIStripping(unittest.TestCase):
    """Test that PII is removed from events."""

    def test_pii_stripped_from_event(self):
        """customer_email, customer_phone, customer_name removed."""
        event = {
            "event_type": "booking_confirmed",
            "customer_email": "strip@me.com",
            "customer_phone": "+1555000",
            "customer_name": "Test Patient",
            "session_id": "sess_abc",
        }
        strip_pii_from_event(event)
        self.assertNotIn("customer_email", event)
        self.assertNotIn("customer_phone", event)
        self.assertNotIn("customer_name", event)
        self.assertIn("session_id", event)  # non-PII kept

    def test_pii_stripped_from_raw_params(self):
        """PII removed from raw_params dict too."""
        event = {
            "event_type": "purchase",
            "raw_params": {
                "customer_email": "raw@params.com",
                "customer_phone": "+1555111",
                "customer_name": "Raw Name",
                "email": "alt@email.com",
                "phone": "+1555222",
                "name": "Alt Name",
                "amount": "100.00",
            },
        }
        strip_pii_from_event(event)
        raw = event["raw_params"]
        for pii in PII_FIELDS:
            self.assertNotIn(pii, raw, f"{pii} should be stripped from raw_params")
        self.assertIn("amount", raw)  # non-PII kept

    def test_strip_handles_missing_raw_params(self):
        """No crash when raw_params is absent."""
        event = {"event_type": "attended", "customer_email": "no@raw.com"}
        strip_pii_from_event(event)
        self.assertNotIn("customer_email", event)


class TestProcessIdentity(unittest.TestCase):
    """Test the unified process_identity() hook."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.ctx = self.app.app_context()
        self.ctx.push()
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})

    def tearDown(self):
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        self.ctx.pop()

    def test_identity_event_gets_person_id(self):
        """booking_confirmed with email → person_id + hash assigned."""
        event = {
            "event_type": "booking_confirmed",
            "customer_email": "process@test.com",
            "customer_phone": "+15559999",
            "customer_name": "Process Test",
            "occurred_at": datetime.utcnow(),
            "site_id": "scandinavian",
            "raw_params": {
                "customer_email": "process@test.com",
                "customer_name": "Process Test",
            },
        }
        process_identity(event)
        self.assertIn("person_id", event)
        self.assertIn("customer_key_hash", event)
        self.assertEqual(event["customer_key_source"], "both")
        # PII stripped
        self.assertNotIn("customer_email", event)
        self.assertNotIn("customer_phone", event)
        self.assertNotIn("customer_name", event)
        self.assertNotIn("customer_email", event.get("raw_params", {}))

    def test_non_identity_event_unchanged(self):
        """page_view with email → no hashing, no stripping."""
        event = {
            "event_type": "page_view",
            "customer_email": "nostrip@test.com",
            "url": "https://example.com",
        }
        process_identity(event)
        self.assertNotIn("person_id", event)
        self.assertNotIn("customer_key_hash", event)
        # PII is NOT stripped for non-identity events
        self.assertIn("customer_email", event)

    def test_identity_event_without_email(self):
        """booking_confirmed without email/phone → PII stripped, no hash."""
        event = {
            "event_type": "booking_confirmed",
            "customer_name": "No Contact",
            "occurred_at": datetime.utcnow(),
            "raw_params": {"customer_name": "No Contact"},
        }
        process_identity(event)
        self.assertNotIn("person_id", event)
        self.assertNotIn("customer_key_hash", event)
        # PII still stripped for identity event types
        self.assertNotIn("customer_name", event)

    def test_repeat_patient_same_person_id(self):
        """Two booking events with same email → same person_id."""
        for event_type in ["booking_confirmed", "attended"]:
            event = {
                "event_type": event_type,
                "customer_email": "repeat@clinic.com",
                "occurred_at": datetime.utcnow(),
                "site_id": "scandinavian",
                "raw_params": {"customer_email": "repeat@clinic.com"},
            }
            process_identity(event)

        # Both should have created/used the same person
        identities = list(get_collection("identities").find({}))
        self.assertEqual(len(identities), 1)

    def test_all_identity_event_types(self):
        """Every event type in IDENTITY_EVENT_TYPES triggers processing."""
        for et in IDENTITY_EVENT_TYPES:
            event = {
                "event_type": et,
                "customer_email": f"{et}@test.com",
                "occurred_at": datetime.utcnow(),
                "raw_params": {"customer_email": f"{et}@test.com"},
            }
            process_identity(event)
            self.assertIn("customer_key_hash", event, f"{et} should get a hash")
            self.assertNotIn("customer_email", event, f"{et} should strip email")


class TestIdentityEndToEnd(unittest.TestCase):
    """End-to-end tests via /track endpoint."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        get_collection("raw_events").delete_many({})

    def tearDown(self):
        get_collection("identities").delete_many({})
        get_collection("identity_links").delete_many({})
        get_collection("raw_events").delete_many({})
        self.ctx.pop()

    def test_booking_confirmed_via_track(self):
        """POST booking_confirmed with email → stored event has person_id, no email."""
        resp = self.client.post("/track", json={
            "event_type": "booking_confirmed",
            "customer_email": "live@test.com",
            "customer_phone": "+15551234567",
            "customer_name": "Live Test",
            "url": "https://booking.scandinavianclinic.com/confirm",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)

        # Check stored event
        events = list(get_collection("raw_events").find(
            {"event_type": "booking_confirmed"}
        ))
        self.assertGreaterEqual(len(events), 1)
        event = events[-1]
        self.assertIn("person_id", event)
        self.assertIn("customer_key_hash", event)
        self.assertNotIn("customer_email", event)
        self.assertNotIn("customer_phone", event)
        self.assertNotIn("customer_name", event)

    def test_page_view_no_identity_processing(self):
        """POST page_view → no person_id, PII not stripped."""
        resp = self.client.post("/track", json={
            "event_type": "page_view",
            "url": "https://scandinavianclinic.com/about",
            "site_id": "scandinavian",
        })
        self.assertEqual(resp.status_code, 200)

        events = list(get_collection("raw_events").find(
            {"event_type": "page_view"}
        ))
        self.assertGreaterEqual(len(events), 1)
        event = events[-1]
        self.assertNotIn("person_id", event)

    def test_two_bookings_same_email_same_person(self):
        """Two booking events with same email → same person_id in both."""
        for i in range(2):
            self.client.post("/track", json={
                "event_type": "booking_confirmed",
                "customer_email": "same@patient.com",
                "url": "https://booking.scandinavianclinic.com/confirm",
                "site_id": "scandinavian",
            })

        events = list(get_collection("raw_events").find(
            {"event_type": "booking_confirmed"}
        ))
        person_ids = [e["person_id"] for e in events if "person_id" in e]
        self.assertGreaterEqual(len(person_ids), 2)
        # All same person
        self.assertEqual(len(set(person_ids)), 1)

        # Only one identity created
        identities = list(get_collection("identities").find({}))
        self.assertEqual(len(identities), 1)


if __name__ == "__main__":
    unittest.main()
