import sys
from pathlib import Path
import json
from bson import json_util

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def fetch_examples():
    collection = get_collection("raw_events")
    targets = [
        "scandinavianclinic.com",
        "dnstrainer.com",
        "booking.scandinavianclinic.com",
        "booking.dnstrainer.com"
    ]
    
    results = {}
    
    for target in targets:
        # Try finding by host first
        cursor = collection.find({"host": target}).limit(1)
        event = next(iter(cursor), None)
        
        if not event:
            # Try finding by domain
            cursor = collection.find({"domain": target}).limit(1)
            event = next(iter(cursor), None)
        
        if event:
            # Convert BSON to JSON
            results[target] = json.loads(json_util.dumps(event))
        else:
            results[target] = "No event found"
            
    with open("example_events.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Events saved to example_events.json")

if __name__ == "__main__":
    fetch_examples()
