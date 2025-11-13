"""
Simulate random ad click events over a 2-week period.
Generates 50 events and sends them to the /track endpoint.
"""

import sys
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mock_data_generator import get_mock_scenario, generate_gclid, generate_fbclid, generate_igshid, generate_ttclid, generate_msclkid, generate_session_id, generate_campaign_id, generate_adset_id, generate_ad_id

# Base URL for tracking endpoint
BASE_URL = "http://localhost:5000/track"

# Platforms to simulate
PLATFORMS = [
    "Google Ads",
    "Meta",
    "Facebook",
    "Instagram",
    "TikTok",
    "LinkedIn",
    "Microsoft Ads",
    "Email"
]

# Campaign names for variety
CAMPAIGN_NAMES = [
    "Summer_Sale_2025",
    "Winter_Promotion",
    "New_Product_Launch",
    "Holiday_Special",
    "Back_to_School",
    "Black_Friday",
    "Cyber_Monday",
    "Spring_Campaign"
]

AD_NAMES = [
    "Video_Ad_1",
    "Banner_Ad_A",
    "Carousel_Ad",
    "Story_Ad",
    "Search_Ad_1",
    "Display_Ad_B"
]

ADSET_NAMES = [
    "Women_25-35",
    "Men_18-24",
    "Retargeting",
    "Lookalike_Audience",
    "Interest_Based"
]


def generate_event_params(platform, start_date, end_date):
    """
    Generate event parameters for a specific platform.
    
    Args:
        platform (str): Platform name
        start_date (datetime): Start of time range
        end_date (datetime): End of time range
        
    Returns:
        dict: Event parameters
    """
    # Get base scenario for platform
    scenario = get_mock_scenario(platform, use_dynamic_placeholders=False)
    
    # Generate random timestamp within date range
    time_range = (end_date - start_date).total_seconds()
    random_seconds = random.uniform(0, time_range)
    event_time = start_date + timedelta(seconds=random_seconds)
    
    # Build parameters
    params = {
        "utm_source": scenario.get("utm_source", "unknown"),
        "utm_medium": scenario.get("utm_medium", "paid_social"),
        "utm_campaign": random.choice(CAMPAIGN_NAMES),
        "utm_content": random.choice(AD_NAMES),
    }
    
    # Add utm_term for search platforms
    if platform in ["Google Ads", "Microsoft Ads"]:
        params["utm_term"] = random.choice(["keyword1", "keyword2", "keyword3"])
    
    # Add platform-specific parameters
    if platform == "Google Ads":
        params["gclid"] = generate_gclid()
        params["campaign_id"] = generate_campaign_id()
    elif platform in ["Meta", "Facebook", "Instagram"]:
        params["fbclid"] = generate_fbclid()
        params["campaign_id"] = generate_campaign_id()
        params["adset_id"] = generate_adset_id()
        params["ad_id"] = generate_ad_id()
        params["placement"] = random.choice(["feed", "stories", "reels", "messenger"])
        if platform == "Instagram":
            params["igshid"] = generate_igshid()
    elif platform == "TikTok":
        params["ttclid"] = generate_ttclid()
        params["campaign_id"] = generate_campaign_id()
    elif platform == "Microsoft Ads":
        params["msclkid"] = generate_msclkid()
        params["campaign_id"] = generate_campaign_id()
    
    # Add session ID (some events will share sessions)
    if random.random() < 0.3:  # 30% chance to reuse a session
        # In real scenario, we'd track sessions, but for simplicity, generate new
        params["session_id"] = generate_session_id()
    else:
        params["session_id"] = generate_session_id()
    
    return params


def send_event(params, event_num, total):
    """
    Send event to /track endpoint.
    
    Args:
        params (dict): Event parameters
        event_num (int): Event number
        total (int): Total number of events
        
    Returns:
        bool: True if successful
    """
    try:
        response = requests.get(BASE_URL, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print(f"✅ Event {event_num}/{total}: {params.get('utm_source')} - {params.get('utm_campaign')}")
                return True
            else:
                print(f"❌ Event {event_num}/{total}: Error - {data.get('message')}")
                return False
        else:
            print(f"❌ Event {event_num}/{total}: HTTP {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Event {event_num}/{total}: Connection error - Is the Flask app running?")
        return False
    except Exception as e:
        print(f"❌ Event {event_num}/{total}: Error - {str(e)}")
        return False


def main():
    """Main function to simulate events."""
    print("=" * 60)
    print("DNS Tracking - Event Simulation Script")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print(f"Events: 50")
    print(f"Period: 2 weeks")
    print("=" * 60)
    print()
    
    # Calculate date range (2 weeks ago to now)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=14)
    
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print()
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:5000/", timeout=2)
        print("✅ Flask server is running")
    except:
        print("❌ Flask server is not running!")
        print("   Please start the server with: python app.py")
        return
    
    print()
    print("Generating and sending events...")
    print("-" * 60)
    
    # Generate and send 50 events
    successful = 0
    failed = 0
    
    for i in range(1, 51):
        # Randomly select platform
        platform = random.choice(PLATFORMS)
        
        # Generate event parameters
        params = generate_event_params(platform, start_date, end_date)
        
        # Send event
        if send_event(params, i, 50):
            successful += 1
        else:
            failed += 1
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    print("-" * 60)
    print()
    print("=" * 60)
    print("Simulation Complete")
    print("=" * 60)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {successful + failed}")
    print()
    print(f"View events at: http://localhost:5000/dashboard")
    print("=" * 60)


if __name__ == "__main__":
    main()

