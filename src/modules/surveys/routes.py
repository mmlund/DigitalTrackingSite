from flask import request, jsonify
from . import surveys_bp
from .service import SurveyService
from ...database import get_collection
from datetime import datetime

survey_service = SurveyService()

@surveys_bp.route('/trigger', methods=['POST'])
def trigger_survey():
    """
    Trigger a survey for a customer.
    Expected JSON:
    {
        "email": "customer@example.com",
        "survey_type": "standard" (optional)
    }
    """
    data = request.json
    if not data or "email" not in data:
        return jsonify({"error": "Email is required"}), 400

    email = data["email"]
    survey_type = data.get("survey_type", "standard")

    success = survey_service.trigger_survey(email, survey_type)

    if success:
        # Log the trigger
        collection = get_collection("surveys")
        collection.insert_one({
            "email": email,
            "type": survey_type,
            "status": "sent",
            "triggered_at": datetime.utcnow()
        })
        return jsonify({"success": True, "message": "Survey triggered"}), 200
    else:
        return jsonify({"error": "Failed to trigger survey"}), 500

@surveys_bp.route('/response', methods=['POST'])
def submit_response():
    """
    Receive a survey response.
    """
    data = request.json
    collection = get_collection("surveys")
    
    # In a real app, we'd match this to the sent survey ID
    response_entry = {
        "data": data,
        "received_at": datetime.utcnow(),
        "type": "response"
    }
    
    result = collection.insert_one(response_entry)
    
    return jsonify({"success": True, "id": str(result.inserted_id)}), 201
