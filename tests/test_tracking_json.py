import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

class TestTrackingJSON(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('src.blueprints.tracking.store_event')
    def test_track_json_payload(self, mock_store):
        mock_store.return_value = "12345"
        
        # Mock dependencies
        with patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1'), \
             patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0)):
            
            payload = {
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign": "summer_sale",
                "event_type": "click",
                "current_page": "/pricing",
                "previous_page": "/",
                "sequence_step": 2,
                "element_id": "signup-btn",
                "screen_resolution": "1920x1080"
            }
            
            response = self.app.post('/track', 
                                   json=payload,
                                   content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['status'], 'ok')
            
            # Verify store_event was called with correct data
            args, _ = mock_store.call_args
            event_data = args[0]
            
            self.assertEqual(event_data['utm_source'], 'google')
            self.assertEqual(event_data['event_type'], 'click')
            self.assertEqual(event_data['sequence_step'], 2)
            self.assertEqual(event_data['screen_resolution'], '1920x1080')

if __name__ == '__main__':
    unittest.main()
