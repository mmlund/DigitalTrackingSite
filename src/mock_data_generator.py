"""
Mock data generator for testing and development.
Generates realistic test data for different platforms.
"""

import random
import string
import json
from datetime import datetime
from pathlib import Path
from .config import DATA_DIR


MOCK_DATA_FILE = DATA_DIR / "mock_data.json"


def load_mock_data():
    """Load mock data from JSON file."""
    try:
        with open(MOCK_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def generate_random_string(length, prefix="", chars=None):
    """Generate a random string of specified length."""
    if chars is None:
        chars = string.ascii_letters + string.digits
    random_str = ''.join(random.choice(chars) for _ in range(length))
    return prefix + random_str if prefix else random_str


def generate_gclid():
    """Generate a realistic Google Click ID (gclid)."""
    # GCLID format: typically starts with "EAlalQobChMI" or similar
    prefixes = ["EAlalQobChMI", "EAEYalQobChMI", "EAEYagobChMI"]
    prefix = random.choice(prefixes)
    suffix = generate_random_string(12, chars=string.ascii_uppercase + string.digits)
    return prefix + suffix


def generate_fbclid():
    """Generate a realistic Facebook Click ID (fbclid)."""
    # FBCLID format: typically starts with "IwAR"
    prefix = "IwAR"
    suffix = generate_random_string(21, chars=string.ascii_letters + string.digits)
    return prefix + suffix


def generate_igshid():
    """Generate a realistic Instagram Share ID (igshid)."""
    # IGSHID format: typically starts with "MzRIODBIN" or similar
    prefixes = ["MzRIODBIN", "MzUyODBIN", "MzYyODBIN"]
    prefix = random.choice(prefixes)
    suffix = generate_random_string(9, chars=string.ascii_uppercase + string.digits)
    return prefix + suffix


def generate_ttclid():
    """Generate a realistic TikTok Click ID (ttclid)."""
    # TTCLID format: typically starts with "Cj0KCQiA"
    prefix = "Cj0KCQiA"
    suffix = generate_random_string(12, chars=string.ascii_letters + string.digits)
    return prefix + suffix


def generate_msclkid():
    """Generate a realistic Microsoft Click ID (msclkid)."""
    # MSCLKID format: alphanumeric string
    return generate_random_string(20, chars=string.ascii_lowercase + string.digits)


def generate_session_id():
    """Generate a realistic session ID."""
    prefix = "sess_"
    suffix = generate_random_string(10, chars=string.ascii_lowercase + string.digits)
    return prefix + suffix


def generate_campaign_id():
    """Generate a realistic campaign ID (numeric)."""
    return str(random.randint(100000000, 999999999))


def generate_adset_id():
    """Generate a realistic ad set ID (numeric)."""
    return str(random.randint(100000000, 999999999))


def generate_ad_id():
    """Generate a realistic ad ID (numeric)."""
    return str(random.randint(100000000, 999999999))


def get_mock_scenario(platform, use_dynamic_placeholders=False):
    """
    Get mock test data for a specific platform.
    
    Args:
        platform (str): Platform name (e.g., "Google Ads", "Meta", "Instagram")
        use_dynamic_placeholders (bool): Whether to use dynamic placeholders in UTM params
        
    Returns:
        dict: Mock data scenario for the platform
    """
    mock_data = load_mock_data()
    scenarios = mock_data.get("test_scenarios", {})
    
    # Map platform names to scenario keys
    platform_map = {
        "Google Ads": "google_ads",
        "Meta": "meta_facebook",
        "Facebook": "meta_facebook",
        "Instagram": "instagram",
        "TikTok": "tiktok",
        "LinkedIn": "linkedin",
        "Microsoft Ads": "microsoft_ads",
        "Email": "email"
    }
    
    scenario_key = platform_map.get(platform, "google_ads")
    scenario = scenarios.get(scenario_key, {}).copy()
    
    # If using dynamic placeholders, keep them; otherwise use example values
    if not use_dynamic_placeholders:
        example_placeholders = mock_data.get("example_placeholders", {})
        if "{{campaign.name}}" in scenario.get("utm_campaign", ""):
            scenario["utm_campaign"] = example_placeholders.get("campaign", {}).get("name", "Summer_Sale_2025")
        if "{{ad.name}}" in scenario.get("utm_content", ""):
            scenario["utm_content"] = example_placeholders.get("ad", {}).get("name", "Video_Ad_1")
        if "{{adset.name}}" in scenario.get("utm_term", ""):
            scenario["utm_term"] = example_placeholders.get("adset", {}).get("name", "Women_25-35")
    
    # Generate fresh IDs and timestamps
    scenario["timestamp"] = datetime.now().isoformat() + "Z"
    scenario["session_id"] = generate_session_id()
    
    # Generate platform-specific IDs if they exist
    if "campaign_id" in scenario:
        scenario["campaign_id"] = generate_campaign_id()
    if "adset_id" in scenario:
        scenario["adset_id"] = generate_adset_id()
    if "ad_id" in scenario:
        scenario["ad_id"] = generate_ad_id()
    
    # Generate platform-specific click IDs
    if "gclid" in scenario:
        scenario["gclid"] = generate_gclid()
    if "fbclid" in scenario:
        scenario["fbclid"] = generate_fbclid()
    if "igshid" in scenario:
        scenario["igshid"] = generate_igshid()
    if "ttclid" in scenario:
        scenario["ttclid"] = generate_ttclid()
    if "msclkid" in scenario:
        scenario["msclkid"] = generate_msclkid()
    
    return scenario


def build_full_url_with_platform_params(base_url, platform, utm_params, use_dynamic_placeholders=False):
    """
    Build a full URL including both UTM parameters and platform-specific parameters.
    This simulates what the URL would look like when it arrives at your site.
    
    Args:
        base_url (str): Base URL (e.g., "http://dnstrainer.com/landing")
        platform (str): Platform name
        utm_params (dict): UTM parameters from URL generator
        use_dynamic_placeholders (bool): Whether placeholders were used
        
    Returns:
        str: Full URL with all parameters
    """
    from urllib.parse import urlencode
    
    # Get mock scenario for platform
    mock_scenario = get_mock_scenario(platform, use_dynamic_placeholders)
    
    # Combine UTM params with platform-specific params
    all_params = {}
    
    # Add UTM parameters
    all_params.update(utm_params)
    
    # Add platform-specific parameters (excluding UTM params already added)
    platform_params = {
        "gclid": mock_scenario.get("gclid"),
        "fbclid": mock_scenario.get("fbclid"),
        "igshid": mock_scenario.get("igshid"),
        "ttclid": mock_scenario.get("ttclid"),
        "msclkid": mock_scenario.get("msclkid"),
        "campaign_id": mock_scenario.get("campaign_id"),
        "adset_id": mock_scenario.get("adset_id"),
        "ad_id": mock_scenario.get("ad_id"),
        "placement": mock_scenario.get("placement")
    }
    
    # Only add non-None platform params
    for key, value in platform_params.items():
        if value is not None:
            all_params[key] = value
    
    # Build query string
    query_string = urlencode(all_params)
    return f"{base_url}?{query_string}"


def get_example_placeholders():
    """Get example placeholder values for display in UI."""
    mock_data = load_mock_data()
    return mock_data.get("example_placeholders", {})

