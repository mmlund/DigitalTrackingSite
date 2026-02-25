from flask import Blueprint, request, jsonify
from src.track_handler import process_tracking_event, store_event, get_client_ip
from src.identity_service import process_identity
from src.cancellation_service import enrich_cancellation_event
from src.rate_limiter import is_rate_limited
from src.database import get_collection
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
        'https://scandinavianclinic.com',
        'https://www.scandinavianclinic.com',
        'https://booking.scandinavianclinic.com',
        'https://www.booking.scandinavianclinic.com',
        'https://stage.scandinavianclinic.com',
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

        # Phase 3A: Identity resolution + PII stripping
        process_identity(event_data)

        # Phase 3B: Cancellation enrichment + dedupe
        if event_data.get("event_type") == "booking_cancelled":
            enrich_cancellation_event(event_data)
            # Dedupe: if dedupe_key already exists, return ok without storing
            dk = event_data.get("dedupe_key")
            if dk:
                existing = get_collection("raw_events").find_one({"dedupe_key": dk})
                if existing:
                    response = jsonify({"status": "ok", "id": str(existing.get("_id", "")), "dedupe": "skipped"})
                    return add_cors_headers(response), 200
        
        # Store event in MongoDB
        doc_id = store_event(event_data)
        
        # Phase 2A: Auto-update campaign actual dates when matching UTM campaign seen
        try:
            utm_obj = event_data.get("utm", {})
            utm_campaign = utm_obj.get("campaign") if isinstance(utm_obj, dict) else None
            if utm_campaign:
                from src.campaign_service import update_campaign_dates_from_event
                occurred_at = event_data.get("occurred_at")
                update_campaign_dates_from_event(utm_campaign, occurred_at)
        except Exception:
            pass  # Never block tracking for campaign date updates
        
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
