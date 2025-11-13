"""
Configuration and data loading for URL generator.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory (project root)
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Configuration file paths
UTM_SOURCES_FILE = DATA_DIR / "utm_sources.json"
UTM_MEDIUMS_FILE = DATA_DIR / "utm_mediums.json"
URL_HISTORY_FILE = DATA_DIR / "url_history.json"

# Base URL for tracking
BASE_URL = "http://dnstrainer.com/landing"

# Test mode configuration
# Set TEST_MODE=True in environment variable or .env file to enable test mode
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"


def load_json_file(file_path):
    """Load JSON file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def get_utm_sources():
    """Load UTM source definitions."""
    data = load_json_file(UTM_SOURCES_FILE)
    return data.get("utm_sources", {})


def get_utm_mediums():
    """Load UTM medium options."""
    data = load_json_file(UTM_MEDIUMS_FILE)
    return data.get("utm_mediums", [])


def load_url_history():
    """Load URL generation history."""
    data = load_json_file(URL_HISTORY_FILE)
    return data.get("url_history", [])


def save_url_history(history):
    """Save URL generation history to file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(URL_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump({"url_history": history}, f, indent=2, ensure_ascii=False)


def is_test_mode():
    """Check if test mode is enabled."""
    return TEST_MODE


# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "dns_tracking")

