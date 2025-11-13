"""
Flask web application for URL generator.
"""

from flask import Flask, render_template, request, jsonify
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.url_generator import generate_url_data, build_tracking_url
from src.validators import validate_all_inputs
from src.config import get_utm_sources, get_utm_mediums, load_url_history, save_url_history, is_test_mode, BASE_URL
from src.platform_suggestions import get_platform_suggestion
from src.mock_data_generator import get_example_placeholders, build_full_url_with_platform_params
from src.track_handler import process_tracking_event, store_event, get_client_ip
from src.rate_limiter import is_rate_limited, get_rate_limit_info
from src.database import get_events, count_events, get_unique_values

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change in production


@app.route('/')
def index():
    """Render the main form page."""
    utm_sources = get_utm_sources()
    utm_mediums = get_utm_mediums()
    test_mode = is_test_mode()
    mock_data = {}
    
    if test_mode:
        mock_data = {
            "example_placeholders": get_example_placeholders(),
            "test_mode": True
        }
    else:
        mock_data = {
            "test_mode": False
        }
    
    return render_template('index.html', 
                         utm_sources=utm_sources, 
                         utm_mediums=utm_mediums,
                         test_mode=test_mode,
                         mock_data=mock_data)


@app.route('/api/platform-suggestion', methods=['POST'])
def get_platform_suggestion_api():
    """Get platform suggestion for utm_source and utm_medium."""
    data = request.get_json()
    platform = data.get('platform', '')
    
    suggestion = get_platform_suggestion(platform)
    if suggestion:
        return jsonify({
            'success': True,
            'utm_source': suggestion.get('utm_source', ''),
            'utm_medium': suggestion.get('utm_medium', '')
        })
    else:
        return jsonify({
            'success': False,
            'utm_source': '',
            'utm_medium': ''
        })


@app.route('/api/generate', methods=['POST'])
def generate_url():
    """Generate tracking URL from form inputs."""
    data = request.get_json()
    
    # Extract form data
    platform = data.get('platform', '')
    utm_source = data.get('utm_source', '').strip()
    utm_medium = data.get('utm_medium', '').strip()
    campaign_name = data.get('campaign_name', '').strip()
    ad_name = data.get('ad_name', '').strip()
    adset_name = data.get('adset_name', '').strip()
    use_dynamic = data.get('use_dynamic_placeholders', False)
    
    # Validate inputs
    is_valid, errors = validate_all_inputs(
        utm_source=utm_source,
        utm_medium=utm_medium,
        campaign_name=campaign_name,
        ad_name=ad_name,
        adset_name=adset_name,
        use_dynamic=use_dynamic
    )
    
    if not is_valid:
        return jsonify({
            'success': False,
            'errors': errors
        }), 400
    
    # Generate URL
    try:
        url_data = generate_url_data(
            platform=platform,
            utm_source=utm_source,
            utm_medium=utm_medium,
            campaign_name=campaign_name,
            ad_name=ad_name,
            adset_name=adset_name,
            use_dynamic_placeholders=use_dynamic
        )
        
        # Save to history
        history = load_url_history()
        history.append(url_data)
        # Keep only last 100 entries
        history = history[-100:]
        save_url_history(history)
        
        return jsonify({
            'success': True,
            'url': url_data['generated_url'],
            'data': url_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get URL generation history."""
    history = load_url_history()
    # Return most recent first
    history.reverse()
    return jsonify({
        'success': True,
        'history': history
    })


@app.route('/api/preview-full-url', methods=['POST'])
def preview_full_url():
    """Preview full URL with platform-specific parameters (test mode only)."""
    if not is_test_mode():
        return jsonify({
            'success': False,
            'error': 'Preview mode is only available in test mode'
        }), 403
    
    data = request.get_json()
    
    # Extract form data
    platform = data.get('platform', '')
    utm_source = data.get('utm_source', '').strip()
    utm_medium = data.get('utm_medium', '').strip()
    campaign_name = data.get('campaign_name', '').strip()
    ad_name = data.get('ad_name', '').strip()
    adset_name = data.get('adset_name', '').strip()
    use_dynamic = data.get('use_dynamic_placeholders', False)
    
    # Validate inputs
    is_valid, errors = validate_all_inputs(
        utm_source=utm_source,
        utm_medium=utm_medium,
        campaign_name=campaign_name,
        ad_name=ad_name,
        adset_name=adset_name,
        use_dynamic=use_dynamic
    )
    
    if not is_valid:
        return jsonify({
            'success': False,
            'errors': errors
        }), 400
    
    try:
        # Build UTM-only URL first
        utm_url = build_tracking_url(
            utm_source=utm_source,
            utm_medium=utm_medium,
            campaign_name=campaign_name,
            ad_name=ad_name,
            adset_name=adset_name,
            use_dynamic_placeholders=use_dynamic
        )
        
        # Extract UTM parameters from URL
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(utm_url)
        utm_params = parse_qs(parsed.query)
        # Convert from list values to single values
        utm_params = {k: v[0] if isinstance(v, list) and len(v) > 0 else v for k, v in utm_params.items()}
        
        # Build full URL with platform parameters
        full_url = build_full_url_with_platform_params(
            base_url=BASE_URL,
            platform=platform,
            utm_params=utm_params,
            use_dynamic_placeholders=use_dynamic
        )
        
        return jsonify({
            'success': True,
            'utm_only_url': utm_url,
            'full_url': full_url,
            'platform': platform
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/track', methods=['GET', 'POST'])
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
        import logging
        logging.error(f"Error in /track endpoint: {e}")
        return jsonify({
            "status": "error",
            "message": "Internal server error"
        }), 500


@app.route('/dashboard')
def dashboard():
    """Render the tracking events dashboard."""
    return render_template('dashboard.html')


@app.route('/api/events', methods=['GET'])
def get_events_api():
    """
    API endpoint to fetch tracking events with filtering.
    Supports filtering by campaign_id, utm_source, and date range.
    """
    try:
        # Get filter parameters
        campaign_id = request.args.get('campaign_id', '').strip()
        utm_source = request.args.get('utm_source', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 25))
        
        # Build filter dictionary
        filter_dict = {}
        
        if campaign_id:
            filter_dict["campaign_id"] = campaign_id
        
        if utm_source:
            filter_dict["utm_source"] = utm_source
        
        if date_from or date_to:
            from datetime import datetime
            date_filter = {}
            if date_from:
                try:
                    date_filter["$gte"] = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                except:
                    pass
            if date_to:
                try:
                    # Add one day to include the entire end date
                    end_date = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
                    from datetime import timedelta
                    date_filter["$lte"] = end_date + timedelta(days=1)
                except:
                    pass
            if date_filter:
                filter_dict["timestamp"] = date_filter
        
        # Calculate pagination
        skip = (page - 1) * limit
        
        # Get events
        events = get_events(filter_dict=filter_dict, limit=limit, skip=skip)
        total_count = count_events(filter_dict=filter_dict)
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        
        return jsonify({
            "success": True,
            "events": events,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "total_pages": total_pages
            }
        })
        
    except Exception as e:
        import logging
        logging.error(f"Error in /api/events: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/events/filters', methods=['GET'])
def get_filter_options():
    """Get unique values for filter dropdowns."""
    try:
        campaign_ids = get_unique_values("campaign_id")
        utm_sources = get_unique_values("utm_source")
        
        return jsonify({
            "success": True,
            "campaign_ids": sorted([c for c in campaign_ids if c]),
            "utm_sources": sorted([u for u in utm_sources if u])
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

