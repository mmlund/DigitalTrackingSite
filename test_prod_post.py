import requests
import json
from datetime import datetime

BASE_URL = "https://digitaltrackingsite.onrender.com/track"

def test_prod_post():
    print(f"Testing production POST endpoint: {BASE_URL}")
    print("-" * 60)
    
    data = {
        "utm_source": "test_script_post",
        "utm_medium": "verification_post",
        "utm_campaign": "prod_test_post",
        "event_type": "test_event_post",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    try:
        print("Sending POST request...")
        response = requests.post(
            BASE_URL, 
            json=data, 
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("[PASS] POST Request successful")
            return True
        else:
            print(f"[FAIL] POST Request failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    test_prod_post()
