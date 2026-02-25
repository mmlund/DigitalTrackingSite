"""
Unit tests for Phase 1 envelope fields in track_handler.process_tracking_event().
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app


class TestEnvelopeFields(unittest.TestCase):
    """Tests that the envelope fields are correctly populated on every event."""

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def _post_event(self, payload, mock_store):
        """Helper: POST a JSON payload to /track and return the event_data passed to store_event."""
        mock_store.return_value = "test_id"
        with patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1'), \
             patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0)):
            response = self.app.post('/track', json=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}: {response.data}")
        args, _ = mock_store.call_args
        return args[0]

    # ── 1. occurred_at from raw_params.timestamp ─────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_occurred_at_from_raw_params_timestamp(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://booking.dnstrainer.com/index.php",
            "site_id": "dnstrainer",
            "timestamp": "2026-02-25T12:00:00Z"
        }
        event = self._post_event(payload, mock_store)
        self.assertIn("occurred_at", event)
        self.assertIsInstance(event["occurred_at"], datetime)
        self.assertEqual(event["occurred_at"].year, 2026)
        self.assertEqual(event["occurred_at"].month, 2)
        self.assertEqual(event["occurred_at"].day, 25)

    # ── 2. occurred_at falls back to server time ─────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_occurred_at_falls_back_to_server_time(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://booking.dnstrainer.com/index.php",
            "site_id": "dnstrainer"
            # No timestamp field
        }
        event = self._post_event(payload, mock_store)
        self.assertIn("occurred_at", event)
        self.assertIsInstance(event["occurred_at"], datetime)
        # Should be very recent (within last 5 seconds)
        diff = (datetime.utcnow() - event["occurred_at"]).total_seconds()
        self.assertLess(diff, 5)

    # ── 3. utm object populated ──────────────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_utm_object_populated(self, mock_store):
        payload = {
            "event_type": "page_view",
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "summer_sale",
            "utm_term": "dns training",
            "utm_content": "ad_v1",
            "site_id": "dnstrainer"
        }
        event = self._post_event(payload, mock_store)
        self.assertIn("utm", event)
        self.assertEqual(event["utm"]["source"], "google")
        self.assertEqual(event["utm"]["medium"], "cpc")
        self.assertEqual(event["utm"]["campaign"], "summer_sale")
        self.assertEqual(event["utm"]["term"], "dns training")
        self.assertEqual(event["utm"]["content"], "ad_v1")

    # ── 4. utm empty strings become None ─────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_utm_object_empty_strings_become_none(self, mock_store):
        payload = {
            "event_type": "booking_confirmed",
            "site_id": "dnstrainer",
            "utm_source": "",
            "utm_medium": "",
            "utm_campaign": ""
        }
        event = self._post_event(payload, mock_store)
        self.assertIsNone(event["utm"]["source"])
        self.assertIsNone(event["utm"]["medium"])
        self.assertIsNone(event["utm"]["campaign"])

    # ── 5. source_system from booking host ───────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_source_system_from_booking_host(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://booking.dnstrainer.com/index.php",
            "site_id": "dnstrainer"
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["source_system"], "easyappointments_dnstrainer")

    # ── 6. source_system from utm_source ─────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_source_system_from_utm(self, mock_store):
        payload = {
            "event_type": "booking_confirmed",
            "utm_source": "easyappointments_scandinavian",
            "utm_medium": "backend",
            "utm_campaign": "booking_confirmation",
            "site_id": "scandinavian"
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["source_system"], "easyappointments_scandinavian")

    # ── 7. source_system defaults to web ─────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_source_system_defaults_to_web(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://dnstrainer.com/",
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "summer"
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["source_system"], "web")

    # ── 8. schema_version present ────────────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_schema_version_present(self, mock_store):
        payload = {
            "event_type": "page_view",
            "site_id": "dnstrainer",
            "utm_source": "direct",
            "utm_medium": "organic",
            "utm_campaign": "general"
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["schema_version"], 1)

    # ── 9. site_id inferred from host ────────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_site_id_inferred_from_host(self, mock_store):
        payload = {
            "event_type": "scroll",
            "url": "https://booking.scandinavianclinic.com/index.php"
            # No explicit site_id
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["site_id"], "scandinavian")

    # ── 10. site_id defaults to unknown ──────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_site_id_defaults_to_unknown(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://some-random-site.com/"
            # No site_id, unrecognized host
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["site_id"], "unknown")

    # ── 11. event_type defaults to unknown ───────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_event_type_defaults_to_unknown(self, mock_store):
        payload = {
            "url": "https://booking.dnstrainer.com/index.php",
            "site_id": "dnstrainer"
            # No event_type at all, and no UTMs.
            # With the fix, this should NOT be rejected — event_type defaults
            # to "unknown" BEFORE the UTM validation gate runs.
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["event_type"], "unknown")

    # ── 12. visitor_id from device_id ────────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_visitor_id_from_device_id(self, mock_store):
        payload = {
            "event_type": "page_view",
            "url": "https://booking.dnstrainer.com/index.php",
            "site_id": "dnstrainer",
            "device_id": "dvc_abc123def456"
        }
        event = self._post_event(payload, mock_store)
        self.assertEqual(event["visitor_id"], "dvc_abc123def456")

    # ── 13. raw_params preserved ─────────────────────────────────

    @patch('src.blueprints.tracking.store_event')
    def test_raw_params_preserved(self, mock_store):
        payload = {
            "event_type": "purchase",
            "url": "https://booking.dnstrainer.com/confirmation",
            "site_id": "dnstrainer",
            "revenue": 105,
            "currency": "CAD",
            "transaction_id": "EA-99"
        }
        event = self._post_event(payload, mock_store)
        self.assertIn("raw_params", event)
        self.assertEqual(event["raw_params"]["revenue"], 105)
        self.assertEqual(event["raw_params"]["currency"], "CAD")
        self.assertEqual(event["raw_params"]["transaction_id"], "EA-99")


if __name__ == '__main__':
    unittest.main()
