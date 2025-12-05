import sys
from pathlib import Path
from datetime import datetime
import time

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def verify_latest_events(limit=5):
    print(f"Checking for latest {limit} events in MongoDB...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Get total count
    count = collection.count_documents({})
    print(f"Total events in DB: {count}")
    
    # Get latest events
    cursor = collection.find().sort("timestamp", -1).limit(limit)
    
    events = list(cursor)
    
    if not events:
        print("No events found.")
        return

    for i, event in enumerate(events):
        timestamp = event.get("timestamp")
        url = event.get("url", "N/A")
        source = event.get("utm_source", "N/A")
        event_type = event.get("event_type", "page_view") # Default to page_view if not specified
        
        print(f"Event {i+1}:")
        print(f"  Time: {timestamp}")
        print(f"  Type: {event_type}")
        print(f"  URL: {url}")
        print(f"  Source: {source}")
        print(f"  ID: {event.get('_id')}")
        print("-" * 30)

if __name__ == "__main__":
    verify_latest_events()
