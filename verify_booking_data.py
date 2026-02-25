import sys
from pathlib import Path
import pprint
import time

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def verify_booking_data():
    print("Verifying Booking Data Collection...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Check for the latest 'booking_confirmed' (backend) or 'purchase' (frontend) events
    # We look for events created in the last few minutes
    
    events = list(collection.find(
        {
            "$or": [
                {"event_type": "booking_confirmed"},
                {"event_type": "purchase"}
            ]
        }
    ).sort("timestamp", -1).limit(5))
    
    if not events:
        print("No booking events found yet.")
        return

    print(f"Found {len(events)} booking events:\n")
    
    for e in events:
        print(f"Event Type: {e.get('event_type')}")
        print(f"Source: {e.get('utm_source', 'N/A')}")
        print(f"Transaction ID: {e.get('transaction_id', 'N/A')}")
        print(f"Customer: {e.get('customer_name', 'N/A')} ({e.get('customer_email', 'N/A')})")
        print(f"Service: {e.get('service_name', 'N/A')}")
        print(f"Revenue: {e.get('revenue', 'N/A')} {e.get('currency', '')}")
        print(f"Timestamp: {e.get('timestamp')}")
        print("-" * 30)

if __name__ == "__main__":
    verify_booking_data()
