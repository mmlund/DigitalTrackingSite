import sys
import os
from pathlib import Path
import json
import unittest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from src.database import get_collection

class TestNewModules(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config['TESTING'] = True
        
        # Set TEST_MODE env var to ensure we use mock DB or safe mode
        # os.environ["TEST_MODE"] = "True"

    def test_therapist_rating(self):
        print("\nTesting Therapist Rating...")
        payload = {
            "therapist_id": "T123",
            "rating": 5,
            "notes": "Great session",
            "patient_id": "P456"
        }
        response = self.client.post('/api/therapist/rating', json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data['success'])
        print(f"Therapist Rating Response: {data}")

        # Verify history
        response = self.client.get('/api/therapist/history/T123')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(len(data['data']) > 0)
        print(f"Therapist History: {len(data['data'])} records")

    def test_survey_trigger(self):
        print("\nTesting Survey Trigger...")
        payload = {
            "email": "test@example.com",
            "survey_type": "feedback"
        }
        response = self.client.post('/api/surveys/trigger', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        print(f"Survey Trigger Response: {data}")

    def test_conversation_logging(self):
        print("\nTesting Conversation Logging...")
        payload = {
            "customer_id": "C789",
            "text": "Hello, I would like to know more about your services. Sure, we offer...",
            "summarize": True
        }
        response = self.client.post('/api/conversations/log', json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data['success'])
        # Summary might be mock or real depending on API key, but field should exist
        self.assertIn('summary', data)
        print(f"Conversation Log Response: {data}")

if __name__ == '__main__':
    unittest.main()
