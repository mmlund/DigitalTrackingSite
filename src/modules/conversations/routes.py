from flask import request, jsonify
from . import conversations_bp
from .service import ConversationService
from ...database import get_collection
from datetime import datetime

conversation_service = ConversationService()

@conversations_bp.route('/log', methods=['POST'])
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
        summary = conversation_service.process_conversation(data["text"])

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
