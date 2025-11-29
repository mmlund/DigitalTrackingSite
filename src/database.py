"""
MongoDB database operations for tracking events.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
from .config import MONGODB_URI, MONGODB_DB_NAME
import logging

logger = logging.getLogger(__name__)

# Global client and database instances
_client = None
_db = None


def get_client():
    """Get or create MongoDB client connection."""
    global _client
    
    if _client is None:
        if not MONGODB_URI:
            raise ValueError("MONGODB_URI not set in environment variables")
        
        try:
            if "<db_password>" in MONGODB_URI:
                raise ValueError("Please replace <db_password> in MONGODB_URI with your actual password")
            
            # Replace <db_password> placeholder if still present (though the check above should catch it)
            uri = MONGODB_URI.replace("<db_password>", "")
            
            _client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                retryWrites=True
            )
            
            # Test connection
            _client.admin.command('ping')
            logger.info("✅ Successfully connected to MongoDB Atlas")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            raise
    
    return _client


def get_database():
    """Get database instance."""
    global _db
    
    if _db is None:
        client = get_client()
        _db = client[MONGODB_DB_NAME]
    
    return _db


def get_collection(collection_name="raw_events"):
    """Get collection instance."""
    db = get_database()
    return db[collection_name]


def test_connection():
    """Test MongoDB connection."""
    try:
        client = get_client()
        client.admin.command('ping')
        db = get_database()
        collections = db.list_collection_names()
        return {
            "status": "success",
            "message": "Connected to MongoDB Atlas",
            "database": MONGODB_DB_NAME,
            "collections": collections
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def create_indexes():
    """Create indexes for efficient querying."""
    collection = get_collection()
    
    indexes = [
        ("timestamp", 1),
        ("campaign_id", 1),
        ("utm_source", 1),
        ("utm_campaign", 1),
        ("session_id", 1),
        ("gclid", 1),
        ("fbclid", 1),
        ("platform_detected", 1),
        ("created_at", 1)
    ]
    
    for field, direction in indexes:
        try:
            collection.create_index([(field, direction)])
            logger.info(f"Created index on {field}")
        except Exception as e:
            logger.warning(f"Index on {field} may already exist: {e}")


def insert_event(event_data):
    """
    Insert a tracking event into the database.
    
    Args:
        event_data (dict): Event data dictionary
        
    Returns:
        str: Inserted document ID
    """
    collection = get_collection()
    
    # Ensure timestamps are set
    if "timestamp" not in event_data:
        event_data["timestamp"] = datetime.utcnow()
    if "created_at" not in event_data:
        event_data["created_at"] = datetime.utcnow()
    
    # Convert datetime if needed
    if isinstance(event_data.get("timestamp"), str):
        try:
            event_data["timestamp"] = datetime.fromisoformat(event_data["timestamp"].replace("Z", "+00:00"))
        except:
            event_data["timestamp"] = datetime.utcnow()
    
    result = collection.insert_one(event_data)
    return str(result.inserted_id)


def get_events(filter_dict=None, limit=25, skip=0, sort_field="timestamp", sort_direction=-1):
    """
    Query events from the database.
    
    Args:
        filter_dict (dict): MongoDB filter dictionary
        limit (int): Maximum number of results
        skip (int): Number of results to skip
        sort_field (str): Field to sort by
        sort_direction (int): 1 for ascending, -1 for descending
        
    Returns:
        list: List of event documents
    """
    collection = get_collection()
    
    if filter_dict is None:
        filter_dict = {}
    
    cursor = collection.find(filter_dict).sort(sort_field, sort_direction).skip(skip).limit(limit)
    
    # Convert ObjectId to string and datetime to ISO format for JSON serialization
    events = []
    for event in cursor:
        event["_id"] = str(event["_id"])
        if isinstance(event.get("timestamp"), datetime):
            event["timestamp"] = event["timestamp"].isoformat()
        if isinstance(event.get("created_at"), datetime):
            event["created_at"] = event["created_at"].isoformat()
        events.append(event)
    
    return events


def count_events(filter_dict=None):
    """Count events matching filter."""
    collection = get_collection()
    
    if filter_dict is None:
        filter_dict = {}
    
    return collection.count_documents(filter_dict)


# Mock Database for testing/fallback
class MockCollection:
    def __init__(self, name, db):
        self.name = name
        self.db = db

    def insert_one(self, document):
        if "_id" not in document:
            document["_id"] = str(uuid.uuid4())
        
        if self.name not in self.db.data:
            self.db.data[self.name] = []
        
        self.db.data[self.name].append(document)
        self.db._save()
            
        return MagicMock(inserted_id=document["_id"])

    def find(self, filter_dict=None):
        results = []
        events = self.db.data.get(self.name, [])
        
        if not filter_dict:
            results = events
        else:
            for event in events:
                match = True
                for k, v in filter_dict.items():
                    if k not in event or event[k] != v:
                        match = False
                        break
                if match:
                    results.append(event)
        
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.skip = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=results)
        cursor.__iter__ = MagicMock(return_value=iter(results))
        return cursor

    def count_documents(self, filter_dict=None):
        cursor = self.find(filter_dict)
        return len(list(cursor))

    def distinct(self, field):
        events = self.db.data.get(self.name, [])
        return list(set(e.get(field) for e in events if field in e))

    def create_index(self, keys):
        pass

class MockDatabase:
    def __init__(self):
        self.data = {}
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MockCollection(name, self)
        return self.collections[name]

    def _save(self):
        # Save to file for persistence in test mode
        try:
            with open("data/mock_db.json", "w") as f:
                # Convert datetime to str for JSON
                json_data = {}
                for col_name, docs in self.data.items():
                    json_data[col_name] = []
                    for doc in docs:
                        doc_copy = doc.copy()
                        for k, v in doc_copy.items():
                            if isinstance(v, datetime):
                                doc_copy[k] = v.isoformat()
                        json_data[col_name].append(doc_copy)
                json.dump(json_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save mock DB: {e}")

import uuid
import json
from unittest.mock import MagicMock

_mock_db = MockDatabase()

def get_collection(collection_name="raw_events"):
    """Get collection instance (or mock)."""
    global _client, _db
    
    try:
        # Try to get real DB
        if _db is None:
            get_database()
        return _db[collection_name]
    except:
        # Fallback to mock
        logger.warning(f"Using Mock Database for collection: {collection_name}")
        return _mock_db[collection_name]


def get_unique_values(field):
    """Get unique values for a field (for filter dropdowns)."""
    collection = get_collection()
    
    return collection.distinct(field)


