
import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app

class TestCORS(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_options_request_allowed_origin(self):
        origin = 'https://dnstrainer.com'
        response = self.app.options('/track', headers={'Origin': origin})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), origin)
        self.assertEqual(response.headers.get('Access-Control-Allow-Credentials'), 'true')
        self.assertEqual(response.headers.get('Access-Control-Allow-Methods'), 'GET, POST, OPTIONS')

    def test_get_request_allowed_origin(self):
        origin = 'https://booking.dnstrainer.com'
        response = self.app.get('/track?utm_source=test', headers={'Origin': origin})
        
        # It might fail validation but headers should still be there
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), origin)
        self.assertEqual(response.headers.get('Access-Control-Allow-Credentials'), 'true')

    def test_no_origin(self):
        response = self.app.options('/track')
        self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), '*')
        # Credentials might not be set or set to true, but with * it's invalid to have credentials true in browser, 
        # but my code sets it only if origin is present.
        self.assertIsNone(response.headers.get('Access-Control-Allow-Credentials'))

if __name__ == '__main__':
    unittest.main()
