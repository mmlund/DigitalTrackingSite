"""
Identity service — Phase 3A

Minimal, privacy-safe patient identity layer.

1. Hash customer_email / customer_phone → customer_key_hash  (SHA-256)
2. Resolve person_id            via deterministic rules
3. Strip PII from event         before storage

All PII (email, phone, name) is removed at ingestion time.
Only the hash + person_id are stored.
"""

import hashlib
import re
import uuid
import logging
from datetime import datetime
from .database import get_collection

logger = logging.getLogger(__name__)

# Event types that carry patient identity information
IDENTITY_EVENT_TYPES = frozenset({
    "booking_confirmed",
    "attended",
    "no_show",
    "booking_cancelled",
    "purchase",
})

# Fields considered PII and stripped from events at ingestion
PII_FIELDS = frozenset({
    "customer_name",
    "customer_email",
    "customer_phone",
    "name",
    "email",
    "phone",
})


# ── Hashing ─────────────────────────────────────────────────────────


def _normalize_email(raw):
    """Lowercase, strip whitespace."""
    if not raw or not isinstance(raw, str):
        return None
    normalized = raw.strip().lower()
    if "@" not in normalized:
        return None
    return normalized


def _normalize_phone(raw):
    """Best-effort E.164: strip non-digit, prepend + if absent."""
    if not raw or not isinstance(raw, str):
        return None
    digits = re.sub(r"[^\d+]", "", raw.strip())
    if not digits or len(digits) < 7:
        return None
    if not digits.startswith("+"):
        # Assume US/CA if 10 digits, else keep as-is
        if len(digits) == 10:
            digits = "+1" + digits
        else:
            digits = "+" + digits
    return digits


def _sha256(prefix, value):
    """SHA-256 of 'prefix:value'."""
    return hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).hexdigest()


def compute_customer_key_hash(email=None, phone=None):
    """
    Compute a deterministic customer_key_hash from available identifiers.

    Priority:
      1. email (preferred — most stable)
      2. phone (fallback)

    Returns:
        (customer_key_hash, customer_key_source)
        customer_key_source ∈ {"email", "phone", "both", "unknown"}
    """
    norm_email = _normalize_email(email)
    norm_phone = _normalize_phone(phone)

    if norm_email and norm_phone:
        return _sha256("email", norm_email), "both"
    elif norm_email:
        return _sha256("email", norm_email), "email"
    elif norm_phone:
        return _sha256("phone", norm_phone), "phone"
    else:
        return None, "unknown"


# ── Identity resolution ─────────────────────────────────────────────


def _now():
    return datetime.utcnow()


def _get_identities_collection():
    return get_collection("identities")


def _get_identity_links_collection():
    return get_collection("identity_links")


def resolve_person_id(
    customer_key_hash,
    occurred_at,
    site_id=None,
    event_type=None,
    session_id=None,
    visitor_id=None,
    source_system=None,
):
    """
    Deterministic identity resolution.

    1. If customer_key_hash exists in any identity's customer_keys[] → return that person_id
    2. Else create a new identity → return new person_id

    Also writes an identity_link record for audit.

    Returns:
        str: person_id (UUID string)
    """
    if not customer_key_hash:
        return None

    col = _get_identities_collection()
    now = _now()

    # ── Lookup existing identity ──
    existing = col.find_one({"customer_keys": customer_key_hash})

    if existing:
        person_id = existing["person_id"]
        # Update last_seen_at
        col.update_one(
            {"person_id": person_id},
            {
                "$set": {
                    "last_seen_at": occurred_at or now,
                    "updated_at": now,
                },
            },
        )
        # Add source_system if new
        if source_system:
            col.update_one(
                {"person_id": person_id},
                {"$addToSet": {"source_systems": source_system}},
            )
    else:
        # ── Create new identity ──
        person_id = str(uuid.uuid4())
        identity_doc = {
            "person_id": person_id,
            "site_id": site_id,
            "customer_keys": [customer_key_hash],
            "first_seen_at": occurred_at or now,
            "last_seen_at": occurred_at or now,
            "source_systems": [source_system] if source_system else [],
            "created_at": now,
            "updated_at": now,
        }
        col.insert_one(identity_doc)
        logger.info(f"Created new identity: person_id={person_id}")

    # ── Write audit link ──
    link_doc = {
        "person_id": person_id,
        "customer_key_hash": customer_key_hash,
        "seen_in_event_type": event_type,
        "seen_at": occurred_at or now,
        "site_id": site_id,
        "source_system": source_system,
        "session_id": session_id,
        "visitor_id": visitor_id,
        "confidence": 1.0,
        "created_at": now,
    }
    _get_identity_links_collection().insert_one(link_doc)

    return person_id


# ── PII stripping ───────────────────────────────────────────────────


def strip_pii_from_event(event_data):
    """
    Remove all PII fields from event_data in-place.

    Removes from top-level AND from raw_params.
    """
    # Top-level PII
    for field in PII_FIELDS:
        event_data.pop(field, None)

    # raw_params PII
    raw = event_data.get("raw_params")
    if isinstance(raw, dict):
        for field in PII_FIELDS:
            raw.pop(field, None)

    return event_data


# ── Convenience: full ingestion hook ────────────────────────────────


def process_identity(event_data):
    """
    Full identity pipeline for a single event.

    If the event type is identity-eligible and has email/phone:
      1. Compute customer_key_hash
      2. Resolve person_id
      3. Attach both to event
      4. Strip all PII

    For non-identity events, this is a no-op.

    Returns:
        event_data (modified in-place)
    """
    event_type = event_data.get("event_type", "")

    if event_type not in IDENTITY_EVENT_TYPES:
        return event_data

    # Extract PII before stripping
    email = (
        event_data.get("customer_email")
        or (event_data.get("raw_params") or {}).get("customer_email")
        or (event_data.get("raw_params") or {}).get("email")
    )
    phone = (
        event_data.get("customer_phone")
        or (event_data.get("raw_params") or {}).get("customer_phone")
        or (event_data.get("raw_params") or {}).get("phone")
    )

    if email or phone:
        key_hash, key_source = compute_customer_key_hash(email, phone)
        if key_hash:
            person_id = resolve_person_id(
                customer_key_hash=key_hash,
                occurred_at=event_data.get("occurred_at"),
                site_id=event_data.get("site_id"),
                event_type=event_type,
                session_id=event_data.get("session_id"),
                visitor_id=event_data.get("visitor_id"),
                source_system=event_data.get("source_system"),
            )
            event_data["customer_key_hash"] = key_hash
            event_data["customer_key_source"] = key_source
            event_data["person_id"] = person_id

    # Always strip PII from identity-eligible events
    strip_pii_from_event(event_data)

    return event_data
