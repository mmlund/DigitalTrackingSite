import sys
from pathlib import Path
import pprint

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def inspect_raw_event():
    print("Inspecting Raw Booking Event...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Get the most recent booking_confirmed event
    event = collection.find_one({"event_type": "booking_confirmed"}, sort=[("timestamp", -1)])
    
    if event:
        print("Raw Event Data:")
        pprint.pprint(event)
    else:
        print("No booking_confirmed event found.")

if __name__ == "__main__":
    inspect_raw_event()
