from flask import Blueprint, request, jsonify
from src.llm.service import llm_service
from src.database import get_events
from datetime import datetime, timedelta

analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

@analysis_bp.route('/ask', methods=['POST'])
def ask_data():
    """
    Ask a question about the marketing data.
    """
    data = request.get_json()
    query = data.get('query')
    
    if not query:
        return jsonify({"success": False, "error": "Query is required"}), 400
        
    # Fetch recent data for context (e.g., last 7 days)
    # In a real system, we'd be smarter about what data to fetch based on the query
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    filter_dict = {
        "timestamp": {
            "$gte": start_date.isoformat(),
            "$lte": end_date.isoformat()
        }
    }
    
    events = get_events(filter_dict=filter_dict, limit=100) # Limit context size
    
    # Prepare context
    context_data = {
        "events": events,
        "count": len(events),
        "period": "last_7_days"
    }
    
    # Get analysis
    try:
        response = llm_service.analyze_marketing_data(context_data, query)
        return jsonify({
            "success": True, 
            "response": response,
            "context_items": len(events)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
