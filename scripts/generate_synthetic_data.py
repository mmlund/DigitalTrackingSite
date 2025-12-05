
"""
Script to generate synthetic tracking data for testing and analysis.
"""

import sys
import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mock_data_generator import get_mock_scenario
from src.database import get_collection, get_client

def generate_synthetic_data(count=1000, days=30):
    """
    Generate synthetic tracking events.
    
    Args:
        count (int): Number of events to generate
        days (int): Time range in days
    """
    print(f"Generating {count} synthetic events over the last {days} days...")
    
    collection = get_collection("raw_events")
    
    platforms = [
        "Google Ads", "Facebook", "Instagram", "TikTok", 
        "LinkedIn", "Microsoft Ads", "Email"
    ]
    weights = [0.4, 0.25, 0.15, 0.1, 0.05, 0.03, 0.02]
    
    events = []
    
    for _ in range(count):
        # Pick a random platform based on weights
        platform = random.choices(platforms, weights=weights)[0]
        
        # Get base scenario
        event = get_mock_scenario(platform, use_dynamic_placeholders=False)
        
        # Randomize timestamp within range
        days_ago = random.uniform(0, days)
        event_time = datetime.utcnow() - timedelta(days=days_ago)
        event["timestamp"] = event_time
        event["created_at"] = event_time
        
        # Add some randomness to user agent and IP (simplified)
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        ]
        event["user_agent"] = random.choice(user_agents)
        
        # Simulate conversion (booking)
        # 5% conversion rate
        if random.random() < 0.05:
            event["event_type"] = "conversion"
            event["conversion_value"] = random.choice([50, 100, 150])
            event["currency"] = "USD"
        else:
            event["event_type"] = "page_view"
            
        events.append(event)
        
    # Bulk insert
    if events:
        collection.insert_many(events)
        print(f"Successfully inserted {len(events)} events into MongoDB.")
    else:
        print("No events generated.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic tracking data")
    parser.add_argument("--count", type=int, default=1000, help="Number of events to generate")
    parser.add_argument("--days", type=int, default=30, help="Time range in days")
    
    args = parser.parse_args()
    
    try:
        generate_synthetic_data(args.count, args.days)
    except Exception as e:
        print(f"Error generating data: {e}")
