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


def compute_dedupe_key(source_system, site_id, appointment_id, cancelled_at):
    """
    Stable dedupe key: SHA-256 of source_system + site_id + appointment_id + cancellation_day.
    cancellation_day is YYYY-MM-DD in UTC derived from cancelled_at.

    This prevents duplicate events if timestamps vary slightly across retries
    on the same day. Original cancelled_at is kept in the payload.
    """
    if not appointment_id:
        return None

    # Determine cancellation day in UTC
    try:
        if isinstance(cancelled_at, str):
            dt = datetime.fromisoformat(cancelled_at.replace("Z", "+00:00"))
        elif isinstance(cancelled_at, datetime):
            dt = cancelled_at
        else:
            return None
        
        # Ensure UTC and extract date
        import datetime as dt_mod
        if dt.tzinfo:
            utc_dt = dt.astimezone(dt_mod.timezone.utc)
        else:
            utc_dt = dt.replace(tzinfo=dt_mod.timezone.utc)
        cancellation_day = utc_dt.strftime("%Y-%m-%d")
    except Exception:
        cancellation_day = "unknown_day"

    raw = f"{source_system or 'unknown'}:{site_id or 'unknown'}:{appointment_id}:{cancellation_day}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Classification ──────────────────────────────────────────────────


def classify_cancellation(appointment_datetime, cancelled_at):
    """
    Classify a cancellation as 'late_cancel' or 'early_cancel'.
    Normalizes both to UTC before comparison.

    Formula: late = cancelled_at_utc >= (appointment_start_utc - 24h)

    Returns:
        (classification, lead_time_hours)
    """
    if not appointment_datetime or not cancelled_at:
        return "unknown", None

    try:
        def _to_utc(dt_val):
            import datetime as dt_mod
            if isinstance(dt_val, str):
                dt_val = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
            if dt_val.tzinfo:
                return dt_val.astimezone(dt_mod.timezone.utc)
            # Default to UTC if naive
            return dt_val.replace(tzinfo=dt_mod.timezone.utc)

        appt_utc = _to_utc(appointment_datetime)
        cancel_utc = _to_utc(cancelled_at)
    except (ValueError, TypeError):
        return "unknown", None

    diff = appt_utc - cancel_utc
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
      - Preserve raw cancelled_by as cancelled_by_raw
      - Validate/default cancelled_by
      - Compute appointment_key (site_id:appointment_id)
      - Compute dedupe_key (stable across retries)
      - Classify late vs early (UTC normalized)
      - Attach lead_time_hours

    Returns:
        event_data (modified in-place)
    """
    # Namespacing: appointment_key
    site_id = event_data.get("site_id") or "unknown"
    appt_id = event_data.get("appointment_id")
    if appt_id:
        event_data["appointment_key"] = f"{site_id}:{appt_id}"

    # Preserve raw cancelled_by and validate
    raw_by = event_data.get("cancelled_by")
    if raw_by:
        event_data["cancelled_by_raw"] = raw_by
    
    cancelled_by = (str(raw_by or "unknown")).lower().strip()
    if cancelled_by not in VALID_CANCELLED_BY:
        logger.warning(f"Invalid cancelled_by '{raw_by}' normalized to 'unknown'")
        cancelled_by = "unknown"
    event_data["cancelled_by"] = cancelled_by

    # Dedupe key (site_id required for stability)
    dedupe_key = compute_dedupe_key(
        event_data.get("source_system"),
        site_id,
        appt_id,
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
