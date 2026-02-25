"""
Comprehensive database audit script to review all tracking data
collected from mock booking appointments.
"""

import sys
import io
from pathlib import Path
from pprint import pformat
from collections import defaultdict

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.database import get_collection

OUTPUT_FILE = Path(__file__).parent / "audit_output.txt"

def audit():
    lines = []
    def p(text=""):
        lines.append(str(text))

    collection = get_collection()

    # 1. Overall counts
    total = collection.count_documents({})
    p("=" * 80)
    p("DATABASE AUDIT REPORT")
    p("=" * 80)
    p(f"\nTotal events in database: {total}\n")

    # 2. Events by type
    p("-" * 60)
    p("EVENTS BY TYPE:")
    p("-" * 60)
    pipeline = [
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for r in collection.aggregate(pipeline):
        p(f"  {r['_id'] or '(none)'}: {r['count']}")

    # 3. Events by domain
    p(f"\n{'-'*60}")
    p("EVENTS BY DOMAIN:")
    p("-" * 60)
    pipeline = [
        {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for r in collection.aggregate(pipeline):
        p(f"  {r['_id'] or '(none)'}: {r['count']}")

    # 4. Events by host (more specific than domain)
    p(f"\n{'-'*60}")
    p("EVENTS BY HOST:")
    p("-" * 60)
    pipeline = [
        {"$group": {"_id": "$host", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for r in collection.aggregate(pipeline):
        p(f"  {r['_id'] or '(none)'}: {r['count']}")

    # 5. Events by site_id
    p(f"\n{'-'*60}")
    p("EVENTS BY SITE_ID:")
    p("-" * 60)
    pipeline = [
        {"$group": {"_id": "$site_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for r in collection.aggregate(pipeline):
        p(f"  {r['_id'] or '(none)'}: {r['count']}")

    # 6. Check for customer data fields (name, email, phone)
    p(f"\n{'-'*60}")
    p("CUSTOMER DATA FIELDS CHECK:")
    p("-" * 60)

    # Check top-level fields
    top_level_fields = [
        "customer_name", "customer_email", "customer_phone",
        "name", "email", "phone",
        "first_name", "last_name"
    ]
    for field in top_level_fields:
        count = collection.count_documents({field: {"$exists": True, "$ne": "", "$ne": None}})
        if count > 0:
            sample = collection.find_one({field: {"$exists": True, "$ne": "", "$ne": None}})
            p(f"  [TOP-LEVEL] '{field}': {count} docs (sample: {sample.get(field)})")
        else:
            p(f"  [TOP-LEVEL] '{field}': NOT FOUND")

    # Check inside raw_params
    p(f"\n  --- Inside raw_params ---")
    raw_params_fields = [
        "raw_params.customer_name", "raw_params.customer_email", "raw_params.customer_phone",
        "raw_params.name", "raw_params.email", "raw_params.phone",
        "raw_params.first_name", "raw_params.last_name",
        "raw_params.customer_first_name", "raw_params.customer_last_name"
    ]
    for field in raw_params_fields:
        count = collection.count_documents({field: {"$exists": True, "$ne": "", "$ne": None}})
        if count > 0:
            sample = collection.find_one({field: {"$exists": True, "$ne": "", "$ne": None}})
            parts = field.split(".")
            val = sample
            for pp in parts:
                val = val.get(pp, {}) if isinstance(val, dict) else None
            p(f"  [RAW_PARAMS] '{field}': {count} docs (sample: {val})")
        else:
            p(f"  [RAW_PARAMS] '{field}': NOT FOUND")

    # 7. Show booking_confirmed and purchase events in detail
    p(f"\n{'-'*60}")
    p("BOOKING/PURCHASE EVENTS (last 10):")
    p("-" * 60)
    events = list(collection.find(
        {"event_type": {"$in": ["booking_confirmed", "purchase"]}}
    ).sort("timestamp", -1).limit(10))

    if not events:
        p("  No booking_confirmed or purchase events found.")
    else:
        for i, e in enumerate(events, 1):
            p(f"\n  --- Event #{i} ---")
            p(f"  Type:        {e.get('event_type')}")
            p(f"  Timestamp:   {e.get('timestamp')}")
            p(f"  Domain:      {e.get('domain')}")
            p(f"  Host:        {e.get('host')}")
            p(f"  Site ID:     {e.get('site_id')}")
            p(f"  UTM Source:  {e.get('utm_source')}")
            for f in ['customer_name', 'customer_email', 'customer_phone', 'name', 'email', 'phone']:
                val = e.get(f)
                if val:
                    p(f"  {f}: {val}")
            rp = e.get('raw_params', {})
            if rp:
                for f in ['customer_name', 'customer_email', 'customer_phone', 'name', 'email', 'phone',
                           'first_name', 'last_name', 'customer_first_name', 'customer_last_name',
                           'service_name', 'revenue', 'transaction_id', 'currency']:
                    val = rp.get(f)
                    if val:
                        p(f"  raw_params.{f}: {val}")

    # 8. Show full raw_params from latest booking events (one per domain)
    p(f"\n{'-'*60}")
    p("FULL RAW_PARAMS SAMPLES:")
    p("-" * 60)
    for evt_type in ["booking_confirmed", "purchase"]:
        sample = collection.find_one(
            {"event_type": evt_type},
            sort=[("timestamp", -1)]
        )
        if sample:
            p(f"\n  Latest '{evt_type}' raw_params:")
            p(pformat(sample.get('raw_params', {}), indent=4))
        else:
            p(f"\n  No '{evt_type}' events found.")

    # 9. Cross-domain breakdown of booking events
    p(f"\n{'-'*60}")
    p("BOOKING EVENTS BY DOMAIN/HOST/SITE_ID:")
    p("-" * 60)
    pipeline = [
        {"$match": {"event_type": {"$in": ["booking_confirmed", "purchase"]}}},
        {"$group": {
            "_id": {"domain": "$domain", "host": "$host", "site_id": "$site_id"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    results = list(collection.aggregate(pipeline))
    if results:
        for r in results:
            p(f"  domain={r['_id'].get('domain')}, host={r['_id'].get('host')}, site_id={r['_id'].get('site_id')}: {r['count']} events")
    else:
        p("  No booking events found.")

    # 10. All unique values
    p(f"\n{'-'*60}")
    p("ALL UNIQUE DOMAINS:")
    p("-" * 60)
    for d in collection.distinct("domain"):
        p(f"  {d}")

    p(f"\nALL UNIQUE HOSTS:")
    for h in collection.distinct("host"):
        p(f"  {h}")

    p(f"\nALL UNIQUE SITE_IDs:")
    for s in collection.distinct("site_id"):
        p(f"  {s}")

    # 11. Date range
    p(f"\n{'-'*60}")
    p("DATA DATE RANGE:")
    p("-" * 60)
    oldest = collection.find_one(sort=[("timestamp", 1)])
    newest = collection.find_one(sort=[("timestamp", -1)])
    if oldest:
        p(f"  Oldest event: {oldest.get('timestamp')}")
    if newest:
        p(f"  Newest event: {newest.get('timestamp')}")

    p(f"\n{'='*80}")
    p("AUDIT COMPLETE")
    p(f"{'='*80}")

    # Write to file
    output = "\n".join(lines)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"Audit written to {OUTPUT_FILE}")

if __name__ == "__main__":
    audit()
