"""
Therapist API routes — schedule, ratings, and completion status.

All endpoints guarded by X-Therapist-Token header.
"""

import os
from functools import wraps
from datetime import datetime, timedelta

from flask import request, jsonify
from . import therapist_bp
from ...database import get_collection
from ...ratings_service import (
    save_day_ratings,
    get_day_ratings,
    get_completion_status,
)
from ...ea_proxy import get_appointments_for_date


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def require_therapist_token(f):
    """Simple token auth guard."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Therapist-Token", "")
        expected = os.getenv("THERAPIST_API_TOKEN", "dev-therapist-token")
        if not token or token != expected:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Schedule endpoint
# ---------------------------------------------------------------------------

@therapist_bp.route('/schedule', methods=['GET'])
@require_therapist_token
def get_schedule():
    """
    GET /api/therapist/schedule?date=YYYY-MM-DD

    Returns combined appointments for a date from both EA instances.
    Defaults to tomorrow if no date given.
    """
    date_str = request.args.get("date")
    if not date_str:
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")

    appointments = get_appointments_for_date(date_str)

    # Format for table display
    rows = []
    for a in appointments:
        # Parse time from start_datetime
        start = a.get("start_datetime", "")
        try:
            dt = datetime.fromisoformat(start)
            date_display = dt.strftime("%Y-%m-%d")
            time_display = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            date_display = date_str
            time_display = start

        rows.append({
            "appointment_id": a["appointment_id"],
            "date": date_display,
            "time": time_display,
            "name": a["patient_name"],
            "paid": "Yes" if a.get("paid") else "No",
            "site": a.get("site_label", a.get("site_id", "")),
            "site_id": a.get("site_id", ""),
            "start_datetime": start,
        })

    return jsonify({
        "success": True,
        "date": date_str,
        "appointments": rows,
        "count": len(rows),
    })


# ---------------------------------------------------------------------------
# Ratings endpoints
# ---------------------------------------------------------------------------

@therapist_bp.route('/ratings/day', methods=['GET'])
@require_therapist_token
def get_ratings_for_day():
    """
    GET /api/therapist/ratings/day?date=YYYY-MM-DD&therapist_id=...

    Returns saved ratings + appointment schedule for a date.
    """
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    therapist_id = request.args.get("therapist_id", "therapist_main")

    # Get appointments from EA
    appointments = get_appointments_for_date(date_str)

    # Get existing ratings
    saved = get_day_ratings(therapist_id, date_str)
    saved_map = {(r["appointment_id"], r["site_id"]): r for r in saved}

    # Merge: appointments with any existing ratings overlayed
    rows = []
    for a in appointments:
        key = (a["appointment_id"], a.get("site_id", ""))
        existing = saved_map.get(key, {})

        start = a.get("start_datetime", "")
        try:
            dt = datetime.fromisoformat(start)
            date_display = dt.strftime("%Y-%m-%d")
            time_display = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            date_display = date_str
            time_display = start

        rows.append({
            "appointment_id": a["appointment_id"],
            "date": date_display,
            "time": time_display,
            "name": a["patient_name"],
            "site": a.get("site_label", a.get("site_id", "")),
            "site_id": a.get("site_id", ""),
            "start_datetime": start,
            # Existing rating values (or defaults)
            "no_show_or_late_cancellation": existing.get("no_show_or_late_cancellation", False),
            "suitability_score": existing.get("suitability_score"),
            "satisfaction_score": existing.get("satisfaction_score"),
            "has_rating": bool(existing),
        })

    return jsonify({
        "success": True,
        "date": date_str,
        "therapist_id": therapist_id,
        "appointments": rows,
        "count": len(rows),
    })


@therapist_bp.route('/ratings/day', methods=['POST'])
@require_therapist_token
def submit_ratings_for_day():
    """
    POST /api/therapist/ratings/day

    Expected JSON:
    {
        "therapist_id": "therapist_main",
        "date": "2025-03-01",
        "ratings": [
            {
                "appointment_id": "EA-42",
                "site_id": "scandinavian",
                "appointment_start_datetime": "2025-03-01T10:00:00",
                "patient_name": "John Doe",
                "no_show_or_late_cancellation": false,
                "suitability_score": 4,
                "satisfaction_score": 5
            }
        ]
    }
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    therapist_id = data.get("therapist_id", "therapist_main")
    date_str = data.get("date")
    ratings = data.get("ratings", [])

    if not date_str:
        return jsonify({"error": "date is required"}), 400
    if not ratings:
        return jsonify({"error": "ratings list is required"}), 400

    result = save_day_ratings(therapist_id, date_str, ratings)

    status_code = 200 if not result["errors"] else 207  # Multi-status
    return jsonify({"success": True, **result}), status_code


@therapist_bp.route('/ratings/status', methods=['GET'])
@require_therapist_token
def get_ratings_status():
    """
    GET /api/therapist/ratings/status?date=YYYY-MM-DD&therapist_id=...

    Returns completion status for a date.
    """
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    therapist_id = request.args.get("therapist_id", "therapist_main")
    status = get_completion_status(therapist_id, date_str)

    return jsonify({"success": True, **status})


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

@therapist_bp.route('/rating', methods=['POST'])
def submit_rating():
    """
    Submit a single rating (legacy endpoint).
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    required_fields = ["therapist_id", "rating"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400

    collection = get_collection("therapist_ratings")

    rating_entry = {
        "therapist_id": data["therapist_id"],
        "patient_id": data.get("patient_id"),
        "rating": data["rating"],
        "relevance_score": data.get("relevance_score"),
        "notes": data.get("notes"),
        "date": data.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
        "created_at": datetime.utcnow()
    }

    result = collection.insert_one(rating_entry)

    return jsonify({
        "success": True,
        "id": str(result.inserted_id),
        "message": "Rating submitted successfully"
    }), 201


@therapist_bp.route('/history/<therapist_id>', methods=['GET'])
def get_history(therapist_id):
    """Get rating history for a therapist."""
    collection = get_collection("therapist_ratings")
    ratings = list(collection.find({"therapist_id": therapist_id}).sort("created_at", -1).limit(50))

    for r in ratings:
        r["_id"] = str(r["_id"])
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()

    return jsonify({"success": True, "data": ratings})
