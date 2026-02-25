"""
Cancellation service — Phase 3B

Handles:
1. Dedupe key computation for idempotent cancellation ingestion
2. Late vs early cancellation classification
3. Event enrichment (dedupe, classification, field validation)
"""

import hashlib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Cancellations < this many hours before appointment = late
LATE_CANCEL_THRESHOLD_HOURS = 24

# Valid values for cancelled_by
VALID_CANCELLED_BY = frozenset({"patient", "admin", "system", "unknown"})


# ── Dedupe ──────────────────────────────────────────────────────────


def compute_dedupe_key(source_system, appointment_id, cancelled_at):
    """
    SHA-256 of source_system + appointment_id + cancelled_at.

    This prevents the same cancellation from being recorded twice
    even if the webhook fires multiple times.
    """
    if not appointment_id:
        return None

    ts = ""
    if isinstance(cancelled_at, datetime):
        ts = cancelled_at.isoformat()
    elif isinstance(cancelled_at, str):
        ts = cancelled_at
    else:
        ts = str(cancelled_at or "")

    raw = f"{source_system or 'unknown'}:{appointment_id}:{ts}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Classification ──────────────────────────────────────────────────


def classify_cancellation(appointment_datetime, cancelled_at):
    """
    Classify a cancellation as 'late_cancel' or 'early_cancel'.

    Returns:
        (classification, lead_time_hours)
    """
    if not appointment_datetime or not cancelled_at:
        return "unknown", None

    if isinstance(appointment_datetime, str):
        try:
            appointment_datetime = datetime.fromisoformat(
                appointment_datetime.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return "unknown", None

    if isinstance(cancelled_at, str):
        try:
            cancelled_at = datetime.fromisoformat(
                cancelled_at.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            return "unknown", None

    diff = appointment_datetime - cancelled_at
    lead_time_hours = round(diff.total_seconds() / 3600, 2)

    if lead_time_hours < 0:
        # Cancelled after appointment time — treat as late
        classification = "late_cancel"
    elif lead_time_hours < LATE_CANCEL_THRESHOLD_HOURS:
        classification = "late_cancel"
    else:
        classification = "early_cancel"

    return classification, lead_time_hours


# ── Enrichment ──────────────────────────────────────────────────────


def enrich_cancellation_event(event_data):
    """
    Enrich a booking_cancelled event in-place:
      - Validate/default cancelled_by
      - Compute dedupe_key
      - Classify late vs early
      - Attach lead_time_hours

    Returns:
        event_data (modified in-place)
    """
    # Validate cancelled_by
    cancelled_by = (event_data.get("cancelled_by") or "unknown").lower().strip()
    if cancelled_by not in VALID_CANCELLED_BY:
        cancelled_by = "unknown"
    event_data["cancelled_by"] = cancelled_by

    # Dedupe key
    dedupe_key = compute_dedupe_key(
        event_data.get("source_system"),
        event_data.get("appointment_id"),
        event_data.get("occurred_at"),
    )
    if dedupe_key:
        event_data["dedupe_key"] = dedupe_key

    # Classification
    classification, lead_time_hours = classify_cancellation(
        event_data.get("appointment_datetime"),
        event_data.get("occurred_at"),
    )
    event_data["cancel_classification"] = classification
    if lead_time_hours is not None:
        event_data["lead_time_hours"] = lead_time_hours

    return event_data
