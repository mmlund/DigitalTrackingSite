from flask import request, jsonify
from . import therapist_bp
from ...database import get_collection
from datetime import datetime

@therapist_bp.route('/rating', methods=['POST'])
def submit_rating():
    """
    Submit a daily rating or patient rating.
    Expected JSON:
    {
        "therapist_id": "string",
        "patient_id": "string (optional)",
        "rating": int (1-5 or 1-10),
        "relevance_score": int (optional),
        "notes": "string",
        "date": "YYYY-MM-DD (optional, defaults to today)"
    }
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
    
    # Convert ObjectId to str
    for r in ratings:
        r["_id"] = str(r["_id"])
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()

    return jsonify({"success": True, "data": ratings})
