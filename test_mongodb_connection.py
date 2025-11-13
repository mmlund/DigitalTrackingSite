"""
Test script to verify MongoDB Atlas connection.
Run this before implementing Phase 2 features.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import test_connection, create_indexes

if __name__ == "__main__":
    print("Testing MongoDB Atlas connection...")
    print("-" * 50)
    
    result = test_connection()
    
    if result["status"] == "success":
        print(f"✅ {result['message']}")
        print(f"📊 Database: {result['database']}")
        print(f"📁 Collections: {result.get('collections', [])}")
        print("\nCreating indexes...")
        create_indexes()
        print("✅ Indexes created successfully!")
    else:
        print(f"❌ Connection failed: {result['message']}")
        print("\nTroubleshooting:")
        print("1. Check that MONGODB_URI in .env file has your actual password (not <db_password>)")
        print("2. Verify your IP address is whitelisted in MongoDB Atlas Network Access")
        print("3. Check that your database user has read/write permissions")
        sys.exit(1)

