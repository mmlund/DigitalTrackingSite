"""
Tests for campaign auto-date updates via atomic $min/$max.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAutoDateUpdates(unittest.TestCase):
    """Test the update_campaign_dates_from_event function."""

    def setUp(self):
        self.mock_col = MagicMock()
        self.patcher = patch('src.campaign_service.get_campaigns_collection', return_value=self.mock_col)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_atomic_min_max_update(self):
        """Verify we use $min for start and $max for end."""
        from src.campaign_service import update_campaign_dates_from_event
        occurred = datetime(2026, 3, 15, 10, 0, 0)

        update_campaign_dates_from_event("spring_2026", occurred)

        self.mock_col.update_many.assert_called_once()
        call_args = self.mock_col.update_many.call_args[0]

        # Check query includes slug and aliases
        query = call_args[0]
        self.assertIn("$or", query)
        or_clauses = query["$or"]
        slugs_queried = [c.get("tracking_defaults.utm_campaign_slug") for c in or_clauses]
        aliases_queried = [c.get("tracking_defaults.utm_campaign_aliases") for c in or_clauses]
        self.assertIn("spring_2026", slugs_queried)
        self.assertIn("spring_2026", aliases_queried)

        # Check update uses $min and $max
        update = call_args[1]
        self.assertIn("$min", update)
        self.assertIn("$max", update)
        self.assertEqual(update["$min"]["dates.actual_start_date"], occurred)
        self.assertEqual(update["$max"]["dates.actual_end_date"], occurred)

    def test_empty_slug_is_noop(self):
        """No DB call when slug is empty."""
        from src.campaign_service import update_campaign_dates_from_event
        update_campaign_dates_from_event("", datetime.utcnow())
        self.mock_col.update_many.assert_not_called()

    def test_none_slug_is_noop(self):
        from src.campaign_service import update_campaign_dates_from_event
        update_campaign_dates_from_event(None, datetime.utcnow())
        self.mock_col.update_many.assert_not_called()

    def test_no_matching_campaign_is_silent(self):
        """update_many with no matches should not raise."""
        from src.campaign_service import update_campaign_dates_from_event
        self.mock_col.update_many.return_value = MagicMock(matched_count=0)
        # Should not raise
        update_campaign_dates_from_event("nonexistent_slug", datetime.utcnow())


class TestAutoDateHookInTracking(unittest.TestCase):
    """Test that the tracking blueprint calls the auto-date hook."""

    def setUp(self):
        from app import app
        self.app = app.test_client()
        self.app.testing = True

    @patch('src.campaign_service.update_campaign_dates_from_event')
    @patch('src.blueprints.tracking.store_event')
    @patch('src.blueprints.tracking.process_tracking_event')
    @patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0))
    @patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1')
    def test_hook_called_when_utm_campaign_present(self, mock_ip, mock_rl, mock_process, mock_store, mock_update):
        mock_process.return_value = {
            "utm": {"campaign": "spring_2026", "source": "google", "medium": "cpc"},
            "occurred_at": datetime(2026, 3, 15),
        }
        mock_store.return_value = "evt123"

        resp = self.app.get('/track?utm_source=google&utm_medium=cpc&utm_campaign=spring_2026')
        self.assertEqual(resp.status_code, 200)
        mock_update.assert_called_once_with("spring_2026", datetime(2026, 3, 15))

    @patch('src.campaign_service.update_campaign_dates_from_event')
    @patch('src.blueprints.tracking.store_event')
    @patch('src.blueprints.tracking.process_tracking_event')
    @patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0))
    @patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1')
    def test_hook_not_called_without_campaign(self, mock_ip, mock_rl, mock_process, mock_store, mock_update):
        mock_process.return_value = {
            "utm": {"source": "google", "medium": "cpc"},
            "occurred_at": datetime(2026, 3, 15),
        }
        mock_store.return_value = "evt456"

        resp = self.app.get('/track?utm_source=google&utm_medium=cpc&event_type=page_view')
        self.assertEqual(resp.status_code, 200)
        mock_update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
