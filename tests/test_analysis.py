import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app

class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('src.blueprints.analysis.get_events')
    def test_ask_data(self, mock_get_events):
        # Mock database return
        mock_get_events.return_value = [
            {"event_type": "page_view", "timestamp": "2025-01-01T12:00:00"},
            {"event_type": "click", "timestamp": "2025-01-01T12:05:00"}
        ]
        
        payload = {
            "query": "How are we doing?"
        }
        
        response = self.app.post('/api/analysis/ask', 
                               json=payload,
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['success'], True)
        self.assertIn("Based on the data", response.json['response'])
        self.assertEqual(response.json['context_items'], 2)

if __name__ == '__main__':
    unittest.main()
