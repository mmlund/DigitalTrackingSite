"""
Backfill script for Phase 3A: Patient Identity

Scans existing raw_events and retroactively:
1. Computes customer_key_hash from embedded customer_email/customer_phone
2. Resolves person_id via identity service
3. Writes customer_key_hash + person_id back to the event
4. Strips PII (customer_email, customer_phone, customer_name) from event

Usage:
    python backfill_identities.py --days 365 --dry-run
    python backfill_identities.py --days 90
"""

import argparse
import sys
import os
import logging
from datetime import datetime, timedelta

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import get_collection
from src.identity_service import (
    IDENTITY_EVENT_TYPES,
    PII_FIELDS,
    compute_customer_key_hash,
    resolve_person_id,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
logger = logging.getLogger(__name__)


def backfill(days=365, dry_run=False):
    """Backfill customer_key_hash and person_id into existing events."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    col = get_collection("raw_events")

    query = {
        "event_type": {"$in": list(IDENTITY_EVENT_TYPES)},
        "occurred_at": {"$gte": cutoff},
    }

    events = list(col.find(query))
    logger.info(f"Found {len(events)} identity-eligible events in last {days} days")

    processed = 0
    skipped = 0
    created = 0

    for event in events:
        event_id = event.get("_id")
        if not event_id:
            skipped += 1
            continue

        # Already has a person_id? Skip.
        if event.get("person_id"):
            skipped += 1
            continue

        # Try to extract email/phone from top-level or raw_params
        email = (
            event.get("customer_email")
            or (event.get("raw_params") or {}).get("customer_email")
            or (event.get("raw_params") or {}).get("email")
        )
        phone = (
            event.get("customer_phone")
            or (event.get("raw_params") or {}).get("customer_phone")
            or (event.get("raw_params") or {}).get("phone")
        )

        if not email and not phone:
            skipped += 1
            continue

        key_hash, key_source = compute_customer_key_hash(email, phone)
        if not key_hash:
            skipped += 1
            continue

        if dry_run:
            logger.info(
                f"[DRY RUN] Would process event {event_id}: "
                f"type={event.get('event_type')}, source={key_source}"
            )
            processed += 1
            continue

        # Resolve person
        person_id = resolve_person_id(
            customer_key_hash=key_hash,
            occurred_at=event.get("occurred_at"),
            site_id=event.get("site_id"),
            event_type=event.get("event_type"),
            session_id=event.get("session_id"),
            visitor_id=event.get("visitor_id"),
            source_system=event.get("source_system"),
        )

        # Build update: set identity fields + strip PII
        set_fields = {
            "customer_key_hash": key_hash,
            "customer_key_source": key_source,
            "person_id": person_id,
        }
        unset_fields = {}
        for pii in PII_FIELDS:
            if pii in event:
                unset_fields[pii] = ""

        update_doc = {"$set": set_fields}
        if unset_fields:
            update_doc["$unset"] = unset_fields

        col.update_one({"_id": event_id}, update_doc)

        # Strip PII from raw_params (requires a separate update since it's nested)
        raw_params = event.get("raw_params", {})
        if isinstance(raw_params, dict):
            changed = False
            for pii in PII_FIELDS:
                if pii in raw_params:
                    del raw_params[pii]
                    changed = True
            if changed:
                col.update_one({"_id": event_id}, {"$set": {"raw_params": raw_params}})

        processed += 1
        logger.info(f"Processed event {event_id} → person_id={person_id}")

    logger.info(
        f"Backfill complete: {processed} processed, {skipped} skipped, "
        f"{len(events)} total scanned"
    )
    return processed, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill patient identities")
    parser.add_argument("--days", type=int, default=365, help="Look back N days")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing",
    )
    args = parser.parse_args()
    backfill(days=args.days, dry_run=args.dry_run)
