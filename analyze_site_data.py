
import sys
from pathlib import Path
from pprint import pprint

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

def analyze_site_data():
    print("Analyzing data separation across sites...")
    print("-" * 60)
    
    collection = get_collection()
    
    # 1. Total event count
    total_count = collection.count_documents({})
    print(f"Total events in database: {total_count}")
    print("-" * 60)

    # 2. Group by Domain
    print("\nEvents by Domain:")
    pipeline_domain = [
        {"$group": {"_id": "$domain", "count": {"$sum": 1}}}
    ]
    results_domain = list(collection.aggregate(pipeline_domain))
    for res in results_domain:
        print(f"  {res['_id']}: {res['count']}")

    # 3. Group by Site ID
    print("\nEvents by Site ID (explicitly provided):")
    pipeline_site_id = [
        {"$group": {"_id": "$site_id", "count": {"$sum": 1}}}
    ]
    results_site_id = list(collection.aggregate(pipeline_site_id))
    for res in results_site_id:
        print(f"  {res['_id']}: {res['count']}")

    # 4. Show samples for each domain
    print("\nSample Data Structure by Domain:")
    unique_domains = collection.distinct("domain")
    
    for domain in unique_domains:
        if not domain: continue
        print(f"\n--- Sample for Domain: {domain} ---")
        sample = collection.find_one({"domain": domain}, {"_id": 0, "session_id": 1, "domain": 1, "subdomain": 1, "host": 1, "site_id": 1, "url": 1, "event_type": 1})
        pprint(sample)

if __name__ == "__main__":
    analyze_site_data()
