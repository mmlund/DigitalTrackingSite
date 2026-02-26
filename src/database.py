"""
MongoDB database operations for tracking events and campaign management.
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import gridfs
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


def get_campaigns_collection():
    """Get campaigns collection."""
    return get_collection("campaigns")


def get_campaign_links_collection():
    """Get campaign_links collection."""
    return get_collection("campaign_links")


def get_campaign_spend_collection():
    """Get campaign_spend collection."""
    return get_collection("campaign_spend")


def get_campaign_assets_collection():
    """Get campaign_assets collection."""
    return get_collection("campaign_assets")


def get_identities_collection():
    """Get identities collection (patient master)."""
    return get_collection("identities")


def get_identity_links_collection():
    """Get identity_links collection (audit trail)."""
    return get_collection("identity_links")


def get_gridfs_bucket(bucket_name="campaign_files"):
    """Get GridFS bucket for file storage."""
    db = get_database()
    return gridfs.GridFS(db, collection=bucket_name)


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
    
    # Legacy indexes (kept for backward compat)
    indexes = [
        ("timestamp", 1),
        ("campaign_id", 1),
        ("utm_source", 1),
        ("utm_campaign", 1),
        ("session_id", 1),
        ("gclid", 1),
        ("fbclid", 1),
        ("platform_detected", 1),
        ("created_at", 1),
        ("event_type", 1),
        ("site_id", 1),
    ]
    
    # Phase 1 envelope indexes
    envelope_indexes = [
        ("occurred_at", 1),
        ("schema_version", 1),
        ("source_system", 1),
    ]
    
    all_indexes = indexes + envelope_indexes
    
    for field, direction in all_indexes:
        try:
            collection.create_index([(field, direction)])
            logger.info(f"Created index on {field}")
        except Exception as e:
            logger.warning(f"Index on {field} may already exist: {e}")
    
    # Compound indexes for common queries
    compound_indexes = [
        [("site_id", 1), ("utm.source", 1)],
        [("site_id", 1), ("event_type", 1)],
        [("site_id", 1), ("occurred_at", -1)],
    ]
    
    for index_spec in compound_indexes:
        try:
            collection.create_index(index_spec)
            field_names = "+".join(f[0] for f in index_spec)
            logger.info(f"Created compound index on {field_names}")
        except Exception as e:
            logger.warning(f"Compound index may already exist: {e}")
    
    # ── Phase 2A: Campaign collection indexes ────────────────────────
    _create_campaign_indexes()

    # ── Phase 3A: Identity indexes ───────────────────────────────────
    _create_identity_indexes()


def _create_campaign_indexes():
    """Create indexes for campaign-related collections."""
    try:
        # campaigns collection
        campaigns = get_campaigns_collection()
        campaigns.create_index([("campaign_id", ASCENDING)], unique=True)
        campaigns.create_index([
            ("site_id", ASCENDING),
            ("channel", ASCENDING),
            ("status", ASCENDING)
        ])
        campaigns.create_index([("tracking_defaults.utm_campaign_slug", ASCENDING)])
        logger.info("Created campaign indexes")
        
        # campaign_links collection
        links = get_campaign_links_collection()
        links.create_index([("campaign_id", ASCENDING)])
        links.create_index([("utm.campaign", ASCENDING)])
        logger.info("Created campaign_links indexes")
        
        # campaign_spend collection
        spend = get_campaign_spend_collection()
        spend.create_index(
            [("campaign_id", ASCENDING), ("month", ASCENDING)],
            unique=True
        )
        logger.info("Created campaign_spend indexes")
        
        # campaign_assets collection
        assets = get_campaign_assets_collection()
        assets.create_index([("campaign_id", ASCENDING)])
        logger.info("Created campaign_assets indexes")
        
    except Exception as e:
        logger.warning(f"Campaign index creation issue: {e}")


def _create_identity_indexes():
    """Create indexes for Phase 3A identity collections."""
    try:
        identities = get_identities_collection()
        identities.create_index([("customer_keys", ASCENDING)])
        identities.create_index([("last_seen_at", ASCENDING)])
        identities.create_index([("person_id", ASCENDING)], unique=True)
        logger.info("Created identities indexes")

        links = get_identity_links_collection()
        links.create_index([("person_id", ASCENDING)])
        links.create_index([("customer_key_hash", ASCENDING)])
        logger.info("Created identity_links indexes")

        # raw_events indexes for person_id queries
        raw = get_collection("raw_events")
        raw.create_index([("person_id", ASCENDING)])
        raw.create_index([("customer_key_hash", ASCENDING)])
        logger.info("Created raw_events identity indexes")

        # Phase 3B: appointment + dedupe indexes
        raw.create_index([("appointment_id", ASCENDING)])
        raw.create_index([("dedupe_key", ASCENDING)], unique=True, sparse=True)
        logger.info("Created raw_events Phase 3B indexes")

    except Exception as e:
        logger.warning(f"Identity index creation issue: {e}")


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

    def _get_nested(self, doc, key):
        """Get value from doc using dot notation (e.g. 'tracking_defaults.utm_source')."""
        parts = key.split('.')
        val = doc
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return None
        return val

    def _set_nested(self, doc, key, value):
        """Set value in doc using dot notation."""
        parts = key.split('.')
        for p in parts[:-1]:
            if p not in doc or not isinstance(doc[p], dict):
                doc[p] = {}
            doc = doc[p]
        doc[parts[-1]] = value

    def _matches(self, doc, filter_dict):
        """Check if doc matches filter. Supports $or, dot-notation, and comparison ops."""
        if not filter_dict:
            return True
        for k, v in filter_dict.items():
            if k == "$or":
                if not any(self._matches(doc, clause) for clause in v):
                    return False
            else:
                doc_val = self._get_nested(doc, k)
                if isinstance(v, dict):
                    # Handle comparison operators
                    for op, op_val in v.items():
                        if op == "$gte":
                            if doc_val is None or doc_val < op_val:
                                return False
                        elif op == "$gt":
                            if doc_val is None or doc_val <= op_val:
                                return False
                        elif op == "$lte":
                            if doc_val is None or doc_val > op_val:
                                return False
                        elif op == "$lt":
                            if doc_val is None or doc_val >= op_val:
                                return False
                        elif op == "$ne":
                            if doc_val == op_val:
                                return False
                        elif op == "$in":
                            if doc_val not in op_val:
                                return False
                        elif op == "$nin":
                            if doc_val in op_val:
                                return False
                elif isinstance(doc_val, list):
                    if v not in doc_val:
                        return False
                elif doc_val != v:
                    return False
        return True

    def insert_one(self, document):
        if "_id" not in document:
            document["_id"] = str(uuid.uuid4())
        
        if self.name not in self.db.data:
            self.db.data[self.name] = []
        
        self.db.data[self.name].append(document)
        self.db._save()
            
        return MagicMock(inserted_id=document["_id"])

    def find(self, filter_dict=None):
        events = self.db.data.get(self.name, [])
        results = [e for e in events if self._matches(e, filter_dict)]
        return MockCursor(results)

    def aggregate(self, pipeline):
        """Simplified aggregate — applies $match only, returns list."""
        events = self.db.data.get(self.name, [])
        results = list(events)
        for stage in pipeline:
            if "$match" in stage:
                results = [e for e in results if self._matches(e, stage["$match"])]
        return results

    def find_one(self, filter_dict=None):
        events = self.db.data.get(self.name, [])
        for e in events:
            if self._matches(e, filter_dict):
                return e
        return None

    def update_one(self, filter_dict, update, upsert=False):
        events = self.db.data.get(self.name, [])
        matched = 0
        modified = 0
        for e in events:
            if self._matches(e, filter_dict):
                self._apply_update(e, update)
                matched = 1
                modified = 1
                break

        if matched == 0 and upsert:
            new_doc = {}
            # Apply $setOnInsert first
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            self._apply_update(new_doc, update)
            self.insert_one(new_doc)
            matched = 1

        self.db._save()
        result = MagicMock()
        result.matched_count = matched
        result.modified_count = modified
        return result

    def update_many(self, filter_dict, update):
        events = self.db.data.get(self.name, [])
        matched = 0
        for e in events:
            if self._matches(e, filter_dict):
                self._apply_update(e, update)
                matched += 1
        self.db._save()
        result = MagicMock()
        result.matched_count = matched
        return result

    def _apply_update(self, doc, update):
        """Apply MongoDB-style update operators ($set, $unset, $min, $max, $addToSet, $push, $inc)."""
        if "$set" in update:
            for k, v in update["$set"].items():
                self._set_nested(doc, k, v)
        if "$unset" in update:
            for k in update["$unset"]:
                if k in doc:
                    del doc[k]
        if "$min" in update:
            for k, v in update["$min"].items():
                cur = self._get_nested(doc, k)
                if cur is None or v < cur:
                    self._set_nested(doc, k, v)
        if "$max" in update:
            for k, v in update["$max"].items():
                cur = self._get_nested(doc, k)
                if cur is None or v > cur:
                    self._set_nested(doc, k, v)
        if "$addToSet" in update:
            for k, v in update["$addToSet"].items():
                cur = self._get_nested(doc, k)
                if cur is None:
                    self._set_nested(doc, k, [v])
                elif isinstance(cur, list):
                    if v not in cur:
                        cur.append(v)
        if "$push" in update:
            for k, v in update["$push"].items():
                cur = self._get_nested(doc, k)
                if cur is None:
                    self._set_nested(doc, k, [v])
                elif isinstance(cur, list):
                    cur.append(v)
        if "$inc" in update:
            for k, v in update["$inc"].items():
                cur = self._get_nested(doc, k)
                if cur is None:
                    self._set_nested(doc, k, v)
                else:
                    self._set_nested(doc, k, cur + v)

    def count_documents(self, filter_dict=None):
        events = self.db.data.get(self.name, [])
        return sum(1 for e in events if self._matches(e, filter_dict))

    def distinct(self, field):
        events = self.db.data.get(self.name, [])
        return list(set(e.get(field) for e in events if field in e))

    def create_index(self, keys, **kwargs):
        pass

    def delete_many(self, filter_dict=None):
        """Delete documents matching filter."""
        events = self.db.data.get(self.name, [])
        if not filter_dict:
            count = len(events)
            self.db.data[self.name] = []
        else:
            keep = [e for e in events if not self._matches(e, filter_dict)]
            count = len(events) - len(keep)
            self.db.data[self.name] = keep
        self.db._save()
        result = MagicMock()
        result.deleted_count = count
        return result


class MockCursor:
    """Chainable cursor for MockCollection.find() results."""

    def __init__(self, results):
        self._results = list(results)
        self._sort_key = None
        self._sort_dir = 1
        self._skip_n = 0
        self._limit_n = None

    def sort(self, key, direction=1):
        if isinstance(key, str):
            self._sort_key = key
            self._sort_dir = direction
        elif isinstance(key, list):
            # [(key, direction)] form — use first key
            self._sort_key = key[0][0]
            self._sort_dir = key[0][1]
        return self

    def skip(self, n):
        self._skip_n = n
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def _resolve(self):
        results = self._results
        if self._sort_key:
            results = sorted(
                results,
                key=lambda d: d.get(self._sort_key) or "",
                reverse=(self._sort_dir == -1),
            )
        if self._skip_n:
            results = results[self._skip_n:]
        if self._limit_n is not None:
            results = results[:self._limit_n]
        return results

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self):
        return len(self._resolve())

    def __list__(self):
        return self._resolve()

    def count(self):
        return len(self._resolve())

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
from .config import MONGODB_URI, MONGODB_DB_NAME, TEST_MODE
import logging

logger = logging.getLogger(__name__)

_mock_db = MockDatabase()

def get_collection(collection_name="raw_events"):
    """Get collection instance (or mock)."""
    global _client, _db
    
    # Force mock mode if TEST_MODE is enabled
    if TEST_MODE:
        if collection_name == "raw_events": # Only log once for main collection
            logger.info(f"Using Mock Database (TEST_MODE=True) for collection: {collection_name}")
        return _mock_db[collection_name]
    
    try:
        # Try to get real DB
        if _db is None:
            get_database()
        return _db[collection_name]
    except Exception as e:
        # Fallback to mock if real DB fails
        logger.warning(f"Connection to real DB failed, falling back to Mock Database: {e}")
        return _mock_db[collection_name]


def get_unique_values(field):
    """Get unique values for a field (for filter dropdowns)."""
    collection = get_collection()
    
    return collection.distinct(field)


