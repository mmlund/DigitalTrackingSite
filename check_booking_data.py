import sys
from pathlib import Path
import pprint

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def check_booking_data():
    print("Checking for booking-specific data (email, revenue, etc.)...")
    print("-" * 60)
    
    collection = get_collection()
    
    # Look for events that might have these fields
    # We check if 'email', 'revenue', 'cost', 'service' exist in any document
    sensitive_fields = ["email", "phone", "name", "customer_name", "revenue", "cost", "price", "service", "service_name"]
    
    found_any = False
    for field in sensitive_fields:
        count = collection.count_documents({field: {"$exists": True}})
        if count > 0:
            print(f"[FOUND] Field '{field}' exists in {count} documents.")
            found_any = True
            
            # Show a sample
            sample = collection.find_one({field: {"$exists": True}})
            print(f"  Sample value: {sample.get(field)}")
        else:
            print(f"[MISSING] Field '{field}' not found in any documents.")
            
    if not found_any:
        print("\nConclusion: No booking-specific customer data found in the database.")

if __name__ == "__main__":
    check_booking_data()
