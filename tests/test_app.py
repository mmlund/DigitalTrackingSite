import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        # Check for some content that should be there
        self.assertIn(b'DNS Tracking URL Generator', response.data)

    def test_dashboard(self):
        response = self.app.get('/dashboard')
        self.assertEqual(response.status_code, 200)

    @patch('src.blueprints.tracking.store_event')
    @patch('src.blueprints.tracking.process_tracking_event')
    def test_track_valid(self, mock_process, mock_store):
        mock_process.return_value = {"some": "data"}
        mock_store.return_value = "12345"
        
        # We need to mock get_client_ip and is_rate_limited too or they might fail/block
        with patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1'), \
             patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0)):
            
            response = self.app.get('/track?utm_source=test&utm_medium=test&utm_campaign=test')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['status'], 'ok')
            self.assertEqual(response.json['id'], '12345')

    def test_track_missing_params(self):
        # We need to mock get_client_ip and is_rate_limited too
        with patch('src.blueprints.tracking.get_client_ip', return_value='127.0.0.1'), \
             patch('src.blueprints.tracking.is_rate_limited', return_value=(False, 10, 0)):
            
            response = self.app.get('/track?utm_source=test')
            # Should fail because medium and campaign are missing
            self.assertEqual(response.status_code, 400)

    @patch('src.blueprints.api.generate_url_data')
    @patch('src.blueprints.api.save_url_history')
    @patch('src.blueprints.api.load_url_history')
    def test_generate_api(self, mock_load, mock_save, mock_generate):
        mock_load.return_value = []
        mock_generate.return_value = {"generated_url": "http://test.com"}
        
        data = {
            "platform": "Instagram",
            "utm_source": "instagram",
            "utm_medium": "paid_social",
            "campaign_name": "Test",
            "ad_name": "Test",
            "adset_name": "Test"
        }
        
        response = self.app.post('/api/generate', 
                               json=data,
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['success'], True)

if __name__ == '__main__':
    unittest.main()
