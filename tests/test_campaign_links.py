"""
Tests for campaign link generation — verifying UTM inheritance from tracking_defaults.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCampaignLinks(unittest.TestCase):
    """Test link generation inherits base UTMs and handles content/term."""

    def setUp(self):
        self.mock_campaign_col = MagicMock()
        self.mock_links_col = MagicMock()

        # Sample campaign returned by get_campaign
        self.sample_campaign = {
            "_id": "abc",
            "campaign_id": "c1",
            "site_id": "dnstrainer",
            "name": "Test",
            "tracking_defaults": {
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign_slug": "spring_2026",
                "utm_campaign_aliases": [],
            },
            "landing_pages": ["https://dnstrainer.com/book"],
            "dates": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        self.patchers = [
            patch('src.campaign_service.get_campaigns_collection', return_value=self.mock_campaign_col),
            patch('src.campaign_service.get_campaign_links_collection', return_value=self.mock_links_col),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()

    def test_generate_link_inherits_base_utms(self):
        from src.campaign_service import generate_campaign_link
        self.mock_campaign_col.find_one.return_value = dict(self.sample_campaign)

        result = generate_campaign_link("c1", {
            "landing_page": "https://dnstrainer.com/book",
        })

        # Verify UTMs inherited from tracking_defaults
        self.assertEqual(result["utm"]["source"], "google")
        self.assertEqual(result["utm"]["medium"], "cpc")
        self.assertEqual(result["utm"]["campaign"], "spring_2026")
        self.assertIsNone(result["utm"]["content"])
        self.assertIsNone(result["utm"]["term"])
        self.mock_links_col.insert_one.assert_called_once()

    def test_generate_link_with_content_and_term(self):
        from src.campaign_service import generate_campaign_link
        self.mock_campaign_col.find_one.return_value = dict(self.sample_campaign)

        result = generate_campaign_link("c1", {
            "landing_page": "https://dnstrainer.com/book",
            "utm_content": "video_ad_1",
            "utm_term": "back_pain",
        })

        self.assertEqual(result["utm"]["content"], "video_ad_1")
        self.assertEqual(result["utm"]["term"], "back_pain")

    def test_generate_link_missing_landing_page(self):
        from src.campaign_service import generate_campaign_link
        self.mock_campaign_col.find_one.return_value = dict(self.sample_campaign)

        with self.assertRaises(ValueError):
            generate_campaign_link("c1", {"landing_page": ""})

    def test_generate_link_campaign_not_found(self):
        from src.campaign_service import generate_campaign_link
        self.mock_campaign_col.find_one.return_value = None

        with self.assertRaises(ValueError):
            generate_campaign_link("nonexistent", {"landing_page": "https://x.com"})

    def test_generated_url_uses_landing_page(self):
        from src.campaign_service import generate_campaign_link
        self.mock_campaign_col.find_one.return_value = dict(self.sample_campaign)

        result = generate_campaign_link("c1", {
            "landing_page": "https://scandinavianclinic.com/consult",
        })

        self.assertTrue(result["generated_url"].startswith("https://scandinavianclinic.com/consult"))
        self.assertIn("utm_source=google", result["generated_url"])

    def test_list_campaign_links(self):
        from src.campaign_service import list_campaign_links
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"_id": "l1", "link_id": "l1", "campaign_id": "c1", "dates": {},
             "created_at": datetime.utcnow()},
        ]
        self.mock_links_col.find.return_value = mock_cursor

        result = list_campaign_links("c1")
        self.mock_links_col.find.assert_called_with({"campaign_id": "c1"})


if __name__ == '__main__':
    unittest.main()
