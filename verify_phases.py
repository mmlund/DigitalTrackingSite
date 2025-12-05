import sys
from pathlib import Path
import pprint
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def verify_phases_3_and_4():
    print("Verifying Phase 3 (Subdomains) and Phase 4 (UTMs)...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Get all events from the last 5 minutes (approx)
    # Just get the last 10 events to be safe
    events = list(collection.find().sort("timestamp", -1).limit(10))
    
    if not events:
        print("No recent events found.")
        return

    print(f"Found {len(events)} recent events:\n")
    
    for e in events:
        print(f"ID: {e.get('_id')}")
        print(f"Timestamp: {e.get('timestamp')}")
        print(f"URL: {e.get('url')}")
        print(f"Host: {e.get('host')}")
        print(f"Subdomain: {e.get('subdomain')}")
        print(f"UTM Source: {e.get('utm_source')}")
        print(f"UTM Campaign: {e.get('utm_campaign')}")
        print("-" * 30)

if __name__ == "__main__":
    verify_phases_3_and_4()
