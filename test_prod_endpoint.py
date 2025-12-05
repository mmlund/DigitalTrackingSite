import requests
import json
import time
from datetime import datetime

BASE_URL = "https://digitaltrackingsite.onrender.com/track"

def test_prod_endpoint():
    print(f"Testing production endpoint: {BASE_URL}")
    print("-" * 60)
    
    # Test 1: Basic GET Request
    params = {
        "utm_source": "test_script",
        "utm_medium": "verification",
        "utm_campaign": "prod_test",
        "event_type": "test_event",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        print("Sending GET request...")
        response = requests.get(BASE_URL, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("[PASS] Request successful")
            return True
        else:
            print(f"[FAIL] Request failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    test_prod_endpoint()
