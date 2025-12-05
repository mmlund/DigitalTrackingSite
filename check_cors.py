import requests

BASE_URL = "https://digitaltrackingsite.onrender.com/track"

def check_cors():
    print("Checking CORS headers on production...")
    
    headers = {
        "Origin": "https://dnstrainer.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    }
    
    try:
        print("Sending OPTIONS request...")
        response = requests.options(BASE_URL, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print("Headers:")
        for k, v in response.headers.items():
            if "Access-Control" in k:
                print(f"  {k}: {v}")
                
        if response.status_code == 200 and "Access-Control-Allow-Origin" in response.headers:
            print("\n[PASS] CORS Preflight looks correct.")
            return True
        else:
            print("\n[FAIL] CORS Preflight failed or missing headers.")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    check_cors()
