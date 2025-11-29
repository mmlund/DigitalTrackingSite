import os
from dotenv import load_dotenv
import sys

# Force reload of .env
load_dotenv(override=True)

uri = os.getenv("MONGODB_URI")
print(f"DEBUG: MONGODB_URI is set: {bool(uri)}")

if uri:
    if "<db_password>" in uri:
        print("ERROR: Placeholder <db_password> found in URI. Please replace it with your actual password in .env")
    else:
        # Mask password for display
        masked = uri
        if "@" in uri:
            parts = uri.split("@")
            if "//" in parts[0]:
                scheme_auth = parts[0].split("//")
                if ":" in scheme_auth[1]:
                    user_pass = scheme_auth[1].split(":")
                    masked = f"{scheme_auth[0]}//{user_pass[0]}:****@{parts[1]}"
        print(f"DEBUG: URI format seems okay: {masked}")

from src.database import test_connection
print("\nAttempting connection...")
result = test_connection()
print(f"Connection Result: {result}")
