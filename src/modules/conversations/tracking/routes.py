from flask import request, jsonify
from . import tracking_bp
from .service import TrackingService
from ...database import get_collection
from datetime import datetime

tracking_service = TrackingService()

@tracking_bp.route('/conversation', methods=['POST'])
def log_conversation():
    """
    Log a conversation and optionally summarize it.
    Expected JSON:
    {
        "customer_id": "string",
        "text": "Full conversation text...",
        "summarize": true/false
    }
    """
    data = request.json
    if not data or "text" not in data:
        return jsonify({"error": "Text is required"}), 400

    summary = None
    if data.get("summarize"):
        summary = tracking_service.process_conversation(data["text"])

    collection = get_collection("conversations")
    entry = {
        "customer_id": data.get("customer_id"),
        "text": data["text"],
        "summary": summary,
        "created_at": datetime.utcnow()
    }
    
    result = collection.insert_one(entry)
    
    return jsonify({
        "success": True, 
        "id": str(result.inserted_id),
        "summary": summary
    }), 201
