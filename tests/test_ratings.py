"""
Tests for the therapist ratings system: ea_proxy, ratings_service, and API routes.
"""

import os
import sys
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["TESTING"] = "true"
os.environ["THERAPIST_API_TOKEN"] = "test-token-123"

from src.database import get_collection
from src import ratings_service


# ---------------------------------------------------------------------------
# Ratings service tests
# ---------------------------------------------------------------------------

class TestRatingsValidation(unittest.TestCase):
    """Test validation logic."""

    def test_missing_appointment_id(self):
        err = ratings_service._validate_rating({"site_id": "x"})
        self.assertIn("appointment_id", err)

    def test_missing_site_id(self):
        err = ratings_service._validate_rating({"appointment_id": "1"})
        self.assertIn("site_id", err)

    def test_valid_non_noshow(self):
        err = ratings_service._validate_rating({
            "appointment_id": "1",
            "site_id": "scandinavian",
            "suitability_score": 4,
            "satisfaction_score": 5,
        })
        self.assertIsNone(err)

    def test_invalid_score_range(self):
        err = ratings_service._validate_rating({
            "appointment_id": "1",
            "site_id": "scandinavian",
            "suitability_score": 7,
            "satisfaction_score": 5,
        })
        self.assertIn("suitability_score", err)

    def test_zero_score_invalid(self):
        err = ratings_service._validate_rating({
            "appointment_id": "1",
            "site_id": "x",
            "suitability_score": 0,
            "satisfaction_score": 5,
        })
        self.assertIn("suitability_score", err)

    def test_noshow_scores_optional(self):
        err = ratings_service._validate_rating({
            "appointment_id": "1",
            "site_id": "scandinavian",
            "no_show_or_late_cancellation": True,
        })
        self.assertIsNone(err)

    def test_non_noshow_scores_required(self):
        err = ratings_service._validate_rating({
            "appointment_id": "1",
            "site_id": "scandinavian",
            "no_show_or_late_cancellation": False,
        })
        self.assertIn("required", err)


class TestRatingsService(unittest.TestCase):
    """Test save/load/status logic with MockDB."""

    def setUp(self):
        # Clear any existing mock data between tests
        therapist_col = get_collection("therapist_ratings")
        events_col = get_collection("raw_events")
        # Clear data if using mock
        if hasattr(therapist_col, 'db'):
            therapist_col.db.data["therapist_ratings"] = []
            events_col.db.data["raw_events"] = []

    def tearDown(self):
        pass

    def test_save_single_rating(self):
        result = ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 4,
            "satisfaction_score": 5,
        }])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["events_emitted"], 2)  # 1 rating + 1 day-complete

    def test_save_multiple_ratings(self):
        result = ratings_service.save_day_ratings("th1", "2025-03-01", [
            {
                "appointment_id": "A1",
                "site_id": "scandinavian",
                "suitability_score": 4,
                "satisfaction_score": 5,
            },
            {
                "appointment_id": "A2",
                "site_id": "dnstrainer",
                "suitability_score": 3,
                "satisfaction_score": 3,
            },
        ])
        self.assertEqual(result["saved"], 2)
        self.assertTrue(result["day_complete"])

    def test_save_noshow_rating(self):
        result = ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "no_show_or_late_cancellation": True,
        }])
        self.assertEqual(result["saved"], 1)
        self.assertTrue(result["day_complete"])

    def test_save_with_validation_error(self):
        result = ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            # Missing scores for non-noshow
        }])
        self.assertEqual(result["saved"], 0)
        self.assertEqual(len(result["errors"]), 1)

    def test_upsert_preserves_history(self):
        # Insert
        ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 3,
            "satisfaction_score": 3,
        }])

        # Update
        ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 5,
            "satisfaction_score": 5,
        }])

        # Check history
        col = get_collection("therapist_ratings")
        doc = col.find_one({"appointment_id": "A1", "site_id": "scandinavian"})
        self.assertEqual(doc["suitability_score"], 5)
        self.assertEqual(len(doc["history"]), 1)
        self.assertEqual(doc["history"][0]["suitability_score"], 3)
        self.assertEqual(doc["version"], 2)

    def test_get_day_ratings(self):
        ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 4,
            "satisfaction_score": 5,
        }])
        saved = ratings_service.get_day_ratings("th1", "2025-03-01")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["appointment_id"], "A1")

    def test_completion_status_complete(self):
        ratings_service.save_day_ratings("th1", "2025-03-01", [
            {
                "appointment_id": "A1",
                "site_id": "s",
                "suitability_score": 4,
                "satisfaction_score": 5,
            },
            {
                "appointment_id": "A2",
                "site_id": "s",
                "no_show_or_late_cancellation": True,
            },
        ])
        status = ratings_service.get_completion_status("th1", "2025-03-01")
        self.assertTrue(status["complete"])
        self.assertEqual(status["total"], 2)
        self.assertEqual(status["rated"], 2)

    def test_completion_status_incomplete(self):
        # No ratings saved yet
        status = ratings_service.get_completion_status("th1", "2025-03-01")
        self.assertFalse(status["complete"])
        self.assertEqual(status["total"], 0)

    def test_events_emitted(self):
        ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 4,
            "satisfaction_score": 5,
        }])
        events = list(get_collection("raw_events").find({}))
        types = [e["event_type"] for e in events]
        self.assertIn("therapist_ratings_submitted", types)
        self.assertIn("therapist_day_ratings_completed", types)

    def test_event_schema(self):
        ratings_service.save_day_ratings("th1", "2025-03-01", [{
            "appointment_id": "A1",
            "site_id": "scandinavian",
            "suitability_score": 4,
            "satisfaction_score": 5,
        }])
        events = list(get_collection("raw_events").find({}))
        rating_event = [e for e in events if e["event_type"] == "therapist_ratings_submitted"][0]
        self.assertEqual(rating_event["appointment_id"], "A1")
        self.assertEqual(rating_event["suitability_score"], 4)
        self.assertEqual(rating_event["schema_version"], "1.0")


# ---------------------------------------------------------------------------
# EA Proxy tests
# ---------------------------------------------------------------------------

class TestEAProxy(unittest.TestCase):
    """Test EA proxy with mocked HTTP calls."""

    def setUp(self):
        from src import ea_proxy
        ea_proxy.reset_sites()

    @patch.dict(os.environ, {
        "EA_HUB_BASE_URL": "https://hub.example.com/api/v1",
        "EA_HUB_API_TOKEN": "hub-token",
        "EA_SPOKE_BASE_URL": "https://spoke.example.com/api/v1",
        "EA_SPOKE_API_TOKEN": "spoke-token",
    })
    @patch("src.ea_proxy.requests.get")
    def test_combined_appointments(self, mock_get):
        from src.ea_proxy import get_appointments_for_date, reset_sites
        reset_sites()

        # Hub returns 1 appt, Spoke returns 1 appt
        hub_resp = MagicMock()
        hub_resp.status_code = 200
        hub_resp.json.return_value = [{
            "id": 101,
            "start_datetime": "2025-03-01 09:00:00",
            "end_datetime": "2025-03-01 10:00:00",
            "customer": {"first_name": "Alice", "last_name": "Jones"},
            "service": {"name": "Consultation"},
        }]
        hub_resp.raise_for_status = MagicMock()

        spoke_resp = MagicMock()
        spoke_resp.status_code = 200
        spoke_resp.json.return_value = [{
            "id": 202,
            "start_datetime": "2025-03-01 14:00:00",
            "end_datetime": "2025-03-01 15:00:00",
            "customer": {"first_name": "Bob", "last_name": "Smith"},
            "service": {"name": "Training"},
        }]
        spoke_resp.raise_for_status = MagicMock()

        mock_get.side_effect = [hub_resp, spoke_resp]

        result = get_appointments_for_date("2025-03-01")
        self.assertEqual(len(result), 2)
        # Should be sorted by time
        self.assertEqual(result[0]["patient_name"], "Alice Jones")
        self.assertEqual(result[0]["site_id"], "dnstrainer")
        self.assertEqual(result[1]["patient_name"], "Bob Smith")
        self.assertEqual(result[1]["site_id"], "scandinavian")

    @patch.dict(os.environ, {}, clear=True)
    def test_no_sites_configured(self):
        from src.ea_proxy import get_appointments_for_date, reset_sites
        os.environ["TESTING"] = "true"
        reset_sites()
        result = get_appointments_for_date("2025-03-01")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------

class TestTherapistAPI(unittest.TestCase):
    """Test API routes with Flask test client."""

    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.client = self.app.test_client()
        self.headers = {"X-Therapist-Token": "test-token-123"}

    def test_schedule_requires_auth(self):
        resp = self.client.get("/api/therapist/schedule")
        self.assertEqual(resp.status_code, 401)

    def test_schedule_with_auth(self):
        with patch("src.modules.therapist.routes.get_appointments_for_date", return_value=[]):
            resp = self.client.get("/api/therapist/schedule", headers=self.headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])

    def test_ratings_day_get(self):
        with patch("src.modules.therapist.routes.get_appointments_for_date", return_value=[]):
            resp = self.client.get(
                "/api/therapist/ratings/day?date=2025-03-01",
                headers=self.headers,
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 0)

    def test_ratings_submit_requires_date(self):
        resp = self.client.post(
            "/api/therapist/ratings/day",
            headers={**self.headers, "Content-Type": "application/json"},
            data=json.dumps({"therapist_id": "th1", "ratings": []}),
        )
        self.assertEqual(resp.status_code, 400)

    def test_ratings_submit_requires_ratings(self):
        resp = self.client.post(
            "/api/therapist/ratings/day",
            headers={**self.headers, "Content-Type": "application/json"},
            data=json.dumps({"date": "2025-03-01", "ratings": []}),
        )
        self.assertEqual(resp.status_code, 400)

    def test_ratings_status(self):
        resp = self.client.get(
            "/api/therapist/ratings/status?date=2025-03-01",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("complete", data)

    def test_legacy_rating_endpoint(self):
        resp = self.client.post(
            "/api/therapist/rating",
            content_type="application/json",
            data=json.dumps({
                "therapist_id": "th1",
                "rating": 5,
                "relevance_score": 4,
            }),
        )
        self.assertEqual(resp.status_code, 201)


# ---------------------------------------------------------------------------
# Schedule service tests (Scandremind)
# ---------------------------------------------------------------------------

class TestScheduleService(unittest.TestCase):
    """Test HTML generation and reminder body."""

    def test_build_schedule_html_empty(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                        "..", "DNStrainer", "easyappointmentsnov18DNS", "scandremind"))
        try:
            from src.schedule_service import build_schedule_html
            html = build_schedule_html([], "2025-03-01")
            self.assertIn("No appointments", html)
        except ImportError:
            self.skipTest("Scandremind not in path")

    def test_build_schedule_html_with_data(self):
        try:
            from src.schedule_service import build_schedule_html
            appts = [{
                "start_datetime": "2025-03-01 09:00:00",
                "patient_name": "Alice Jones",
                "paid": True,
                "site_label": "DNSTrainer",
            }]
            html = build_schedule_html(appts, "2025-03-01")
            self.assertIn("Alice Jones", html)
            self.assertIn("DNSTrainer", html)
            self.assertIn("Yes", html)
        except ImportError:
            self.skipTest("Scandremind not in path")

    def test_build_reminder_body(self):
        try:
            from src.schedule_service import build_reminder_body
            body = build_reminder_body("https://example.com/ratings", "2025-03-01")
            self.assertIn("https://example.com/ratings", body)
            self.assertIn("2025-03-01", body)
            self.assertNotIn("Second", body)

            followup = build_reminder_body("https://example.com/ratings", "2025-03-01", is_followup=True)
            self.assertIn("Second", followup)
        except ImportError:
            self.skipTest("Scandremind not in path")


if __name__ == "__main__":
    unittest.main()
