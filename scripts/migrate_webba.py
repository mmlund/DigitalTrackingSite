import csv
import os
import sys
import json
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path to allow importing from src
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.identity_service import compute_customer_key_hash, resolve_person_id
from src.database import get_collection

# Load environment variables
load_dotenv(project_root / ".env")

# Global identity cache to avoid redundant network lookups
IDENTITY_CACHE = {}

def normalize_timestamp(ts):
    """Convert Webba Unix timestamp to ISO 8601 string."""
    try:
        if not ts or ts == "0":
            return None
        return datetime.utcfromtimestamp(int(ts)).isoformat() + "Z"
    except (ValueError, TypeError):
        return None

def get_current_value(duration_mins):
    """Map duration to today's value for LTV calculation."""
    mapping = {
        30: 105.0,
        45: 150.0,
        60: 190.0
    }
    return mapping.get(int(duration_mins), 0.0)

def migrate_csv(file_path, event_type, is_cancelled=False):
    """Read Webba CSV and yield event documents."""
    site_id = "scandinavian"
    source_system = "webba_migration"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Map fields
            appointment_id = row.get("id_cancelled") if is_cancelled else row.get("id")
            if not appointment_id:
                continue

            email = row.get("email")
            phone = row.get("phone")
            name = row.get("name")
            
            # Identity Resolution
            key_hash, key_source = compute_customer_key_hash(email, phone)
            person_id = None
            if key_hash:
                # Check cache first
                if key_hash in IDENTITY_CACHE:
                    person_id = IDENTITY_CACHE[key_hash]
                else:
                    # We use the appointment's created_at for resolution timestamp
                    occurred_at_raw = row.get("time")
                    occurred_at = normalize_timestamp(occurred_at_raw)
                    
                    person_id = resolve_person_id(
                        customer_key_hash=key_hash,
                        occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "")) if occurred_at else datetime.utcnow(),
                        site_id=site_id,
                        event_type=event_type,
                        source_system=source_system
                    )
                    # Update cache
                    IDENTITY_CACHE[key_hash] = person_id

            # Build Event Data
            event_data = {
                "event_type": event_type,
                "site_id": site_id,
                "source_system": source_system,
                "schema_version": "1.0.0",
                "occurred_at": normalize_timestamp(row.get("time")),
                "created_at": normalize_timestamp(row.get("created_on")) or datetime.utcnow().isoformat() + "Z",
                "appointment_id": str(appointment_id),
                "person_id": person_id,
                "customer_key_hash": key_hash,
                "customer_key_source": key_source,
                "duration_minutes": int(row.get("duration", 0)),
                "category": row.get("service_id"),
                "raw_status": row.get("status"),
                "value": get_current_value(row.get("duration", 0)),
                "raw_params": {
                    "is_migrated": True,
                    "webba_id": row.get("id"),
                    "webba_service_category": row.get("service_category"),
                    "user_ip": row.get("user_ip"),
                    "historical_value": row.get("paid_amount") or row.get("moment_price") or row.get("amount_paid")
                }
            }
            
            # Generate Dedupe Key (Stable across re-runs)
            dedupe_payload = f"{source_system}:{site_id}:{appointment_id}:{event_type}"
            event_data["dedupe_key"] = hashlib.sha256(dedupe_payload.encode('utf-8')).hexdigest()
            
            yield event_data

def run_migration(appointments_csv, cancelled_csv, dry_run=True):
    print(f"Starting migration (Dry Run: {dry_run})", flush=True)
    
    print(f"Connecting to MongoDB...", flush=True)
    collection = get_collection("raw_events")
    print(f"Connected.", flush=True)
    
    total_processed = 0
    total_inserted = 0
    
    # Process regular appointments
    print(f"Processing appointments...", flush=True)
    for event in migrate_csv(appointments_csv, "appointment_confirmed"):
        total_processed += 1
        if not dry_run:
            try:
                collection.update_one(
                    {"dedupe_key": event["dedupe_key"]},
                    {"$set": event},
                    upsert=True
                )
                total_inserted += 1
                if total_inserted % 25 == 0:
                    print(f"  Processed {total_processed} items. Inserted/Updated {total_inserted} confirmed appointments...", flush=True)
            except Exception as e:
                print(f"Error inserting event {event.get('appointment_id')}: {e}", flush=True)
        else:
            if total_processed <= 5:
                print(f"Sample Confirmed Event: {json.dumps(event, indent=2)}", flush=True)

    # Process cancelled appointments
    print(f"Processing cancellations...", flush=True)
    confirmed_total = total_inserted
    current_can_inserted = 0
    for event in migrate_csv(cancelled_csv, "appointment_cancelled", is_cancelled=True):
        total_processed += 1
        if not dry_run:
            try:
                collection.update_one(
                    {"dedupe_key": event["dedupe_key"]},
                    {"$set": event},
                    upsert=True
                )
                total_inserted += 1
                current_can_inserted += 1
                if current_can_inserted % 25 == 0:
                    print(f"  Processed {total_processed} total items. Inserted {current_can_inserted} cancellations...", flush=True)
            except Exception as e:
                print(f"Error inserting cancelled event {event.get('appointment_id')}: {e}", flush=True)
        else:
            if total_processed % 100 == 0:
                print(f"Processed {total_processed} events (Dry Run)...", flush=True)

    print(f"Migration finished. Total Processed: {total_processed}, Total Inserted/Upserted: {total_inserted}", flush=True)

if __name__ == "__main__":
    base_path = Path("c:/Users/mmlun/Antigravity")
    app_csv = base_path / "wp_5w1cryhtw4_wbk_appointments.csv"
    can_csv = base_path / "wp_5w1cryhtw4_wbk_cancelled_appointments.csv"
    
    is_dry_run = "--real" not in sys.argv
    
    if not app_csv.exists() or not can_csv.exists():
        print(f"Error: CSV files not found.\nExpected: {app_csv}\nAnd: {can_csv}", flush=True)
        sys.exit(1)
        
    run_migration(str(app_csv), str(can_csv), dry_run=is_dry_run)
