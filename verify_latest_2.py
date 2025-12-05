import sys
from pathlib import Path
import pprint
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def verify_latest_2():
    print("Verifying Latest 2 Events...")
    print("-" * 60)
    
    collection = get_collection()
    
    events = list(collection.find().sort("timestamp", -1).limit(2))
    
    if not events:
        print("No recent events found.")
        return

    for e in events:
        print(f"ID: {e.get('_id')}")
        print(f"Timestamp: {e.get('timestamp')}")
        print(f"URL: {e.get('url')}")
        print(f"Host: {e.get('host')}")
        print(f"Subdomain: {e.get('subdomain')}")
        print(f"UTM Source: {e.get('utm_source')}")
        print(f"Event Type: {e.get('event_type')}")
        print("-" * 30)

if __name__ == "__main__":
    verify_latest_2()
