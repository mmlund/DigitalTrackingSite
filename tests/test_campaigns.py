"""
Tests for campaign service CRUD, read-only enforcement, and duplicating.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCampaignCRUD(unittest.TestCase):
    """Test campaign create, read, update, list, duplicate operations."""

    def setUp(self):
        self.mock_col = MagicMock()
        self.patcher = patch('src.campaign_service.get_campaigns_collection', return_value=self.mock_col)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _valid_data(self, **overrides):
        data = {
            "name": "Test Campaign",
            "site_id": "dnstrainer",
            "channel": "google_ads",
            "status": "draft",
            "tracking_defaults": {
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign_slug": "test_spring_2026",
            },
        }
        data.update(overrides)
        return data

    def test_create_campaign_success(self):
        from src.campaign_service import create_campaign
        result = create_campaign(self._valid_data())

        self.mock_col.insert_one.assert_called_once()
        self.assertEqual(result["name"], "Test Campaign")
        self.assertEqual(result["status"], "draft")
        self.assertIsNotNone(result["campaign_id"])
        self.assertIsNone(result["dates"]["actual_start_date"])
        self.assertIsNone(result["notes"])

    def test_create_campaign_missing_name(self):
        from src.campaign_service import create_campaign
        with self.assertRaises(ValueError):
            create_campaign(self._valid_data(name=""))

    def test_create_campaign_missing_utm_source(self):
        from src.campaign_service import create_campaign
        data = self._valid_data()
        data["tracking_defaults"]["utm_source"] = ""
        with self.assertRaises(ValueError):
            create_campaign(data)

    def test_create_campaign_invalid_channel(self):
        from src.campaign_service import create_campaign
        with self.assertRaises(ValueError):
            create_campaign(self._valid_data(channel="invalid"))

    def test_create_campaign_invalid_site(self):
        from src.campaign_service import create_campaign
        with self.assertRaises(ValueError):
            create_campaign(self._valid_data(site_id="invalid"))

    def test_create_campaign_with_notes(self):
        from src.campaign_service import create_campaign
        result = create_campaign(self._valid_data(notes="My campaign notes"))
        self.assertEqual(result["notes"], "My campaign notes")

    def test_get_campaign(self):
        from src.campaign_service import get_campaign
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "name": "Test",
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
            "dates": {},
        }
        result = get_campaign("c1")
        self.assertEqual(result["campaign_id"], "c1")
        self.mock_col.find_one.assert_called_with({"campaign_id": "c1"})

    def test_get_campaign_not_found(self):
        from src.campaign_service import get_campaign
        self.mock_col.find_one.return_value = None
        self.assertIsNone(get_campaign("nonexistent"))

    def test_list_campaigns_with_status_sort(self):
        from src.campaign_service import list_campaigns
        now = datetime.utcnow()
        self.mock_col.find.return_value = [
            {"_id": "1", "status": "ended", "updated_at": now, "dates": {}},
            {"_id": "2", "status": "active", "updated_at": now, "dates": {}},
            {"_id": "3", "status": "draft", "updated_at": now, "dates": {}},
        ]
        result = list_campaigns()
        # Active should be first, then draft, then ended
        self.assertEqual(result[0]["status"], "active")
        self.assertEqual(result[1]["status"], "draft")
        self.assertEqual(result[2]["status"], "ended")

    def test_update_campaign_notes(self):
        from src.campaign_service import update_campaign
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "name": "Test",
            "status": "draft", "dates": {},
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        }
        update_campaign("c1", {"notes": "Updated notes"})
        call_args = self.mock_col.update_one.call_args
        update_set = call_args[0][1]["$set"]
        self.assertEqual(update_set["notes"], "Updated notes")
        self.assertIn("notes_updated_at", update_set)

    def test_update_active_campaign_locked_fields(self):
        """Core tracking fields should be read-only when campaign is active."""
        from src.campaign_service import update_campaign
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "name": "Test",
            "status": "active", "dates": {},
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        }

        # Attempt to modify utm_source should raise
        with self.assertRaises(ValueError) as ctx:
            update_campaign("c1", {"tracking_defaults": {"utm_source": "new_source"}})
        self.assertIn("Cannot modify", str(ctx.exception))

        # Attempt to modify utm_medium should raise
        with self.assertRaises(ValueError) as ctx:
            update_campaign("c1", {"tracking_defaults": {"utm_medium": "new_medium"}})
        self.assertIn("Cannot modify", str(ctx.exception))

        # Attempt to modify utm_campaign_slug should raise
        with self.assertRaises(ValueError) as ctx:
            update_campaign("c1", {"tracking_defaults": {"utm_campaign_slug": "new_slug"}})
        self.assertIn("Cannot modify", str(ctx.exception))

    def test_update_active_campaign_unlocked_fields(self):
        """Non-core fields should remain editable even when active."""
        from src.campaign_service import update_campaign
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "name": "Test",
            "status": "active", "dates": {},
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        }
        # Should not raise
        update_campaign("c1", {
            "notes": "Still editable",
            "landing_pages": ["https://new.com"],
            "tracking_defaults": {"utm_campaign_aliases": ["alias1"]},
        })
        self.mock_col.update_one.assert_called_once()

    def test_set_campaign_status(self):
        from src.campaign_service import set_campaign_status
        self.mock_col.update_one.return_value = MagicMock(matched_count=1)
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "status": "active", "dates": {},
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        }
        result = set_campaign_status("c1", "active")
        self.assertEqual(result["status"], "active")

    def test_set_campaign_status_invalid(self):
        from src.campaign_service import set_campaign_status
        with self.assertRaises(ValueError):
            set_campaign_status("c1", "bogus")

    def test_duplicate_campaign(self):
        from src.campaign_service import duplicate_campaign
        now = datetime.utcnow()
        self.mock_col.find_one.return_value = {
            "_id": "abc", "campaign_id": "c1", "name": "Original",
            "status": "active", "dates": {"actual_start_date": now},
            "tracking_defaults": {"utm_source": "g", "utm_medium": "c", "utm_campaign_slug": "s"},
            "created_at": now, "updated_at": now,
        }
        result = duplicate_campaign("c1")
        self.assertEqual(result["name"], "Original (copy)")
        self.assertEqual(result["status"], "draft")
        self.assertIsNone(result["dates"]["actual_start_date"])
        self.assertNotEqual(result["campaign_id"], "c1")
        self.mock_col.insert_one.assert_called_once()


class TestCampaignConversionEvents(unittest.TestCase):
    """Test that only valid conversion events are accepted."""

    def setUp(self):
        self.mock_col = MagicMock()
        self.patcher = patch('src.campaign_service.get_campaigns_collection', return_value=self.mock_col)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_valid_conversion_events(self):
        from src.campaign_service import create_campaign
        for event in ("booking_confirmed", "purchase", "engaged_session"):
            data = {
                "name": f"Test {event}",
                "tracking_defaults": {
                    "utm_source": "g", "utm_medium": "c",
                    "utm_campaign_slug": f"test_{event}",
                    "expected_conversion_event": event,
                }
            }
            if event == "engaged_session":
                data["tracking_defaults"]["engagement_seconds_threshold"] = 30
            result = create_campaign(data)
            self.assertEqual(result["tracking_defaults"]["expected_conversion_event"], event)

    def test_invalid_conversion_event_rejected(self):
        from src.campaign_service import create_campaign
        data = {
            "name": "Test Invalid",
            "tracking_defaults": {
                "utm_source": "g", "utm_medium": "c",
                "utm_campaign_slug": "test",
                "expected_conversion_event": "campaign_click",
            }
        }
        with self.assertRaises(ValueError):
            create_campaign(data)


if __name__ == '__main__':
    unittest.main()
