"""
Test script for /track endpoint.
Tests various scenarios and validates responses.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000/track"

def test_track_endpoint():
    """Test the /track endpoint with various scenarios."""
    
    print("=" * 70)
    print("DNS Tracking - /track Endpoint Test Suite")
    print("=" * 70)
    print()
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:5000/", timeout=2)
        print("Flask server is running")
    except:
        print("[FAIL] Flask server is not running!")
        print("   Please start the server with: python app.py")
        return False
    
    print()
    print("-" * 70)
    print("Test 1: Basic GET Request (Instagram)")
    print("-" * 70)
    
    params = {
        "utm_source": "instagram",
        "utm_medium": "paid_social",
        "utm_campaign": "Summer_Sale_2025",
        "utm_content": "Video_Ad_1",
        "fbclid": "IwAR1xYzAbC123def456ghi789",
        "campaign_id": "123456789",
        "adset_id": "456789012",
        "ad_id": "789012345",
        "placement": "feed"
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("[PASS] Test 1 PASSED")
        else:
            print("[FAIL] Test 1 FAILED")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print()
    print("-" * 70)
    print("Test 2: Google Ads GET Request")
    print("-" * 70)
    
    params = {
        "utm_source": "google",
        "utm_medium": "paid_search",
        "utm_campaign": "Summer_Sale",
        "utm_content": "Search_Ad_1",
        "utm_term": "keyword_phrase",
        "gclid": "EAlalQobChMI5YyF8Y6AhUJ",
        "campaign_id": "987654321"
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("[PASS] Test 2 PASSED")
        else:
            print("[FAIL] Test 2 FAILED")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print()
    print("-" * 70)
    print("Test 3: POST Request (JSON)")
    print("-" * 70)
    
    data = {
        "utm_source": "facebook",
        "utm_medium": "paid_social",
        "utm_campaign": "Winter_Promotion",
        "utm_content": "Banner_Ad",
        "fbclid": "IwAR2xYzAbC456def789ghi012",
        "campaign_id": "111222333",
        "adset_id": "444555666",
        "ad_id": "777888999"
    }
    
    try:
        response = requests.post(
            BASE_URL,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("[PASS] Test 3 PASSED")
        else:
            print("[FAIL] Test 3 FAILED")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print()
    print("-" * 70)
    print("Test 4: Validation Error (Missing Required Parameters)")
    print("-" * 70)
    
    params = {
        "utm_source": "instagram",
        # Missing utm_medium and utm_campaign
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 400:
            print("[PASS] Test 4 PASSED (Correctly rejected invalid request)")
        else:
            print("[FAIL] Test 4 FAILED (Should return 400)")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print()
    print("-" * 70)
    print("Test 5: TikTok Ads")
    print("-" * 70)
    
    params = {
        "utm_source": "tiktok",
        "utm_medium": "paid_social",
        "utm_campaign": "New_Product_Launch",
        "utm_content": "Video_Ad",
        "ttclid": "Cj0KCQiA123456789",
        "campaign_id": "555666777"
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        if response.status_code == 200:
            print("[PASS] Test 5 PASSED")
        else:
            print("[FAIL] Test 5 FAILED")
    except Exception as e:
        print(f"[FAIL] Error: {e}")
    
    print()
    print("=" * 70)
    print("Test Suite Complete")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Check the dashboard: http://localhost:5000/dashboard")
    print("2. Run simulation script: python scripts/simulate_clicks.py")
    print("=" * 70)


if __name__ == "__main__":
    test_track_endpoint()

