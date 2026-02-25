"""
Tests for campaign spend upsert and listing.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCampaignSpend(unittest.TestCase):
    """Test spend upsert and list operations."""

    def setUp(self):
        self.mock_campaign_col = MagicMock()
        self.mock_spend_col = MagicMock()

        self.sample_campaign = {
            "_id": "abc", "campaign_id": "c1", "name": "Test",
            "dates": {},
            "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
        }

        self.patchers = [
            patch('src.campaign_service.get_campaigns_collection', return_value=self.mock_campaign_col),
            patch('src.campaign_service.get_campaign_spend_collection', return_value=self.mock_spend_col),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_upsert_spend_new(self):
        from src.campaign_service import upsert_spend
        self.mock_campaign_col.find_one.return_value = dict(self.sample_campaign)
        self.mock_spend_col.find_one.return_value = {
            "_id": "s1", "campaign_id": "c1", "month": "2026-03",
            "amount": 500.0, "currency": "USD",
        }

        result = upsert_spend("c1", "2026-03", 500.0)
        self.mock_spend_col.update_one.assert_called_once()
        # Verify upsert=True
        call_kwargs = self.mock_spend_col.update_one.call_args
        self.assertTrue(call_kwargs[1].get("upsert", False) or
                        (len(call_kwargs[0]) > 2 and call_kwargs[0][2]) or
                        call_kwargs.kwargs.get("upsert", False))

    def test_upsert_spend_campaign_not_found(self):
        from src.campaign_service import upsert_spend
        self.mock_campaign_col.find_one.return_value = None

        with self.assertRaises(ValueError):
            upsert_spend("nonexistent", "2026-03", 500.0)

    def test_list_spend_sorted(self):
        from src.campaign_service import list_spend
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"_id": "s1", "campaign_id": "c1", "month": "2026-03", "amount": 500},
            {"_id": "s2", "campaign_id": "c1", "month": "2026-02", "amount": 300},
        ]
        self.mock_spend_col.find.return_value = mock_cursor

        result = list_spend("c1")
        self.mock_spend_col.find.assert_called_with({"campaign_id": "c1"})
        mock_cursor.sort.assert_called_with("month", -1)


if __name__ == '__main__':
    unittest.main()
