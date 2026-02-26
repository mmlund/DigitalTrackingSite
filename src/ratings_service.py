"""
Ratings Service — therapist end-of-day ratings storage + event emission.

Stores ratings in `therapist_ratings` keyed by (appointment_id, site_id).
Supports upsert with audit trail.  Emits structured events to `raw_events`.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from src.database import get_collection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
VALID_SCORES = {1, 2, 3, 4, 5}


def _validate_rating(r: Dict) -> Optional[str]:
    """Return error string if invalid, else None."""
    if not r.get("appointment_id"):
        return "appointment_id is required"
    if not r.get("site_id"):
        return "site_id is required"

    is_noshow = bool(r.get("no_show_or_late_cancellation"))

    # If NOT a no-show, scores are required
    if not is_noshow:
        suit = r.get("suitability_score")
        sat = r.get("satisfaction_score")
        if suit is None or sat is None:
            return "suitability_score and satisfaction_score required (unless no-show)"
        if int(suit) not in VALID_SCORES:
            return f"suitability_score must be 1-5, got {suit}"
        if int(sat) not in VALID_SCORES:
            return f"satisfaction_score must be 1-5, got {sat}"
    else:
        # No-show: scores optional, but validate if provided
        suit = r.get("suitability_score")
        sat = r.get("satisfaction_score")
        if suit is not None and int(suit) not in VALID_SCORES:
            return f"suitability_score must be 1-5, got {suit}"
        if sat is not None and int(sat) not in VALID_SCORES:
            return f"satisfaction_score must be 1-5, got {sat}"

    return None


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def save_day_ratings(
    therapist_id: str,
    date_str: str,
    ratings: List[Dict],
) -> Dict[str, Any]:
    """
    Batch save ratings for a day.  Upserts per (appointment_id, site_id).

    Returns:
        {"saved": int, "errors": list, "events_emitted": int, "day_complete": bool}
    """
    col = get_collection("therapist_ratings")
    events_col = get_collection("raw_events")
    now = datetime.utcnow()

    saved = 0
    errors = []
    events_emitted = 0

    for r in ratings:
        err = _validate_rating(r)
        if err:
            errors.append({"appointment_id": r.get("appointment_id"), "error": err})
            continue

        appt_id = str(r["appointment_id"])
        site_id = r["site_id"]

        suit = int(r["suitability_score"]) if r.get("suitability_score") is not None else None
        sat = int(r["satisfaction_score"]) if r.get("satisfaction_score") is not None else None
        noshow = bool(r.get("no_show_or_late_cancellation", False))

        key = {"appointment_id": appt_id, "site_id": site_id}

        # Check for existing (for audit trail)
        existing = col.find_one(key)

        doc = {
            "appointment_id": appt_id,
            "site_id": site_id,
            "appointment_date": date_str,
            "appointment_start_datetime": r.get("appointment_start_datetime", ""),
            "patient_name": r.get("patient_name", ""),
            "therapist_id": therapist_id,
            "no_show_or_late_cancellation": noshow,
            "suitability_score": suit,
            "satisfaction_score": sat,
            "updated_at": now,
        }

        if existing:
            # Audit: push old values into history
            history_entry = {
                "suitability_score": existing.get("suitability_score"),
                "satisfaction_score": existing.get("satisfaction_score"),
                "no_show_or_late_cancellation": existing.get("no_show_or_late_cancellation"),
                "updated_at": existing.get("updated_at"),
            }
            col.update_one(key, {
                "$set": doc,
                "$push": {"history": history_entry},
                "$inc": {"version": 1},
            })
        else:
            doc["created_at"] = now
            doc["version"] = 1
            doc["history"] = []
            col.insert_one(doc)

        saved += 1

        # Emit per-appointment event
        event = {
            "event_type": "therapist_ratings_submitted",
            "appointment_id": appt_id,
            "site_id": site_id,
            "appointment_start_datetime": r.get("appointment_start_datetime", ""),
            "therapist_id": therapist_id,
            "submitted_at": now,
            "no_show_or_late_cancellation": noshow,
            "suitability_score": suit,
            "satisfaction_score": sat,
            "occurred_at": now,
            "schema_version": "1.0",
        }
        events_col.insert_one(event)
        events_emitted += 1

    # Check completion
    status = get_completion_status(therapist_id, date_str)
    day_complete = status["complete"]

    # Emit day-completion event if all rated
    if day_complete and saved > 0:
        day_event = {
            "event_type": "therapist_day_ratings_completed",
            "date": date_str,
            "therapist_id": therapist_id,
            "site_scope": "combined",
            "num_appointments": status["total"],
            "num_rated": status["rated"],
            "completed_at": now,
            "occurred_at": now,
            "schema_version": "1.0",
        }
        events_col.insert_one(day_event)
        events_emitted += 1

    return {
        "saved": saved,
        "errors": errors,
        "events_emitted": events_emitted,
        "day_complete": day_complete,
    }


def get_day_ratings(therapist_id: str, date_str: str) -> List[Dict]:
    """Get all saved ratings for a therapist on a given date."""
    col = get_collection("therapist_ratings")
    results = list(col.find({
        "therapist_id": therapist_id,
        "appointment_date": date_str,
    }))

    # Clean ObjectId for JSON serialisation
    for r in results:
        r["_id"] = str(r.get("_id", ""))
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].isoformat()
        # Clean history timestamps
        for h in r.get("history", []):
            if isinstance(h.get("updated_at"), datetime):
                h["updated_at"] = h["updated_at"].isoformat()

    return results


def get_completion_status(therapist_id: str, date_str: str) -> Dict[str, Any]:
    """
    Check how many of the day's appointments have been rated.

    Note: 'total' is based on saved ratings, not EA appointments — the caller
    can pass total_appointments from EA proxy if needed for accuracy.
    """
    col = get_collection("therapist_ratings")
    ratings = list(col.find({
        "therapist_id": therapist_id,
        "appointment_date": date_str,
    }))

    total = len(ratings)
    rated = 0
    for r in ratings:
        noshow = r.get("no_show_or_late_cancellation", False)
        has_scores = (
            r.get("suitability_score") is not None
            and r.get("satisfaction_score") is not None
        )
        if noshow or has_scores:
            rated += 1

    # Find completion timestamp
    completed_at = None
    if total > 0 and rated == total:
        # Latest updated_at
        latest = max(
            (r.get("updated_at") or r.get("created_at") for r in ratings),
            default=None,
        )
        if isinstance(latest, datetime):
            completed_at = latest.isoformat()
        elif latest:
            completed_at = str(latest)

    return {
        "date": date_str,
        "therapist_id": therapist_id,
        "total": total,
        "rated": rated,
        "complete": total > 0 and rated == total,
        "completed_at": completed_at,
    }
