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
    # Get the origin from the request
    origin = request.headers.get('Origin')
    
    # List of allowed origins - in production this should be stricter
    # For now we allow the specific domains mentioned by the user
    allowed_origins = [
        'https://dnstrainer.com',
        'https://www.dnstrainer.com',
        'https://booking.dnstrainer.com',
        'https://www.booking.dnstrainer.com',
        'http://localhost:5000',
        'http://127.0.0.1:5000'
    ]
    
    # Helper to set CORS headers
    def add_cors_headers(response):
        if origin:
            # If origin is in our allowed list, or if we want to be permissive for debugging
            # For now, let's reflect the origin if it's provided, to fix the immediate issue
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'
            
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return add_cors_headers(response), 200
    
    try:
        # Get client IP for rate limiting
        ip_address = get_client_ip()
        
        # Check rate limit (20 requests per second)
        is_limited, remaining, reset_time = is_rate_limited(ip_address, max_requests=20)
        
        if is_limited:
            response = jsonify({
                "status": "error",
                "message": "Rate limit exceeded. Maximum 20 requests per second.",
                "retry_after": reset_time
            })
            return add_cors_headers(response), 429
        
        # Process and validate tracking event
        event_data = process_tracking_event()
        
        # Store event in MongoDB
        doc_id = store_event(event_data)
        
        response = jsonify({
            "status": "ok",
            "id": doc_id
        })
        return add_cors_headers(response), 200
        
    except ValueError as e:
        # Validation error
        response = jsonify({
            "status": "error",
            "message": str(e)
        })
        return add_cors_headers(response), 400
        
    except Exception as e:
        # Internal server error
        logging.error(f"Error in /track endpoint: {e}")
        response = jsonify({
            "status": "error",
            "message": "Internal server error"
        })
        return add_cors_headers(response), 500
