import sys
from pathlib import Path
import pprint

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def verify_subdomain_separation():
    print("Verifying Subdomain Separation (Phase 3)...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Find recent events from booking.dnstrainer.com
    booking_events = list(collection.find(
        {"host": {"$regex": "booking.dnstrainer.com"}},
        {"host": 1, "subdomain": 1, "url": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(3))
    
    # Find recent events from dnstrainer.com (excluding booking)
    main_events = list(collection.find(
        {"host": "dnstrainer.com"},
        {"host": 1, "subdomain": 1, "url": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(3))
    
    print("\n--- Booking Subdomain Events ---")
    if booking_events:
        for e in booking_events:
            print(f"Host: {e.get('host')}, Subdomain: {e.get('subdomain')}, URL: {e.get('url')}")
    else:
        print("No events found for booking.dnstrainer.com")

    print("\n--- Main Domain Events ---")
    if main_events:
        for e in main_events:
            print(f"Host: {e.get('host')}, Subdomain: {e.get('subdomain')}, URL: {e.get('url')}")
    else:
        print("No events found for dnstrainer.com")

if __name__ == "__main__":
    verify_subdomain_separation()
