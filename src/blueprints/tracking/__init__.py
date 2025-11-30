from flask import Blueprint, request, jsonify
from src.track_handler import process_tracking_event, store_event, get_client_ip
from src.rate_limiter import is_rate_limited
import logging

tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route('/track', methods=['GET', 'POST', 'OPTIONS'])
def track():
    """
    Tracking endpoint that captures all query parameters and stores them in MongoDB.
    Accepts both GET and POST requests.
    """
    try:
        # Get client IP for rate limiting
        ip_address = get_client_ip()
        
        # Check rate limit (20 requests per second)
        is_limited, remaining, reset_time = is_rate_limited(ip_address, max_requests=20)
        
        if is_limited:
            return jsonify({
                "status": "error",
                "message": "Rate limit exceeded. Maximum 20 requests per second.",
                "retry_after": reset_time
            }), 429
        
        # Process and validate tracking event
        event_data = process_tracking_event()
        
        # Store event in MongoDB
        doc_id = store_event(event_data)
        
        return jsonify({
            "status": "ok",
            "id": doc_id
        }), 200
        
    except ValueError as e:
        # Validation error
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
        
    except Exception as e:
        # Internal server error
        logging.error(f"Error in /track endpoint: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500
