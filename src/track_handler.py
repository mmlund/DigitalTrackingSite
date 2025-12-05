"""
Track handler for processing and storing tracking events.
"""

import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from flask import request
from .database import insert_event, get_collection
from .config import BASE_URL
import logging

logger = logging.getLogger(__name__)

# Session management: 60-minute timeout
SESSION_TIMEOUT = timedelta(minutes=60)
_active_sessions = {}  # Store active sessions: {session_id: last_activity}


def detect_platform(params):
    """
    Auto-detect platform from parameters.
    
    Args:
        params (dict): Request parameters
        
    Returns:
        str: Detected platform name
    """
    if params.get("gclid"):
        return "Google Ads"
    elif params.get("fbclid"):
        if params.get("igshid"):
            return "Instagram"
        return "Meta/Facebook"
    elif params.get("ttclid"):
        return "TikTok"
    elif params.get("msclkid"):
        return "Microsoft Ads"
    elif params.get("utm_source"):
        source = params.get("utm_source", "").lower()
        if "google" in source or "gclid" in source:
            return "Google Ads"
        elif "facebook" in source or "meta" in source:
            return "Meta/Facebook"
        elif "instagram" in source:
            return "Instagram"
        elif "tiktok" in source:
            return "TikTok"
        elif "bing" in source or "microsoft" in source:
            return "Microsoft Ads"
        elif "linkedin" in source:
            return "LinkedIn"
        elif "email" in source or "mailchimp" in source:
            return "Email"
    
    return "Unknown"


def get_or_create_session_id(params, ip_address):
    """
    Get existing session ID or create a new one.
    Sessions expire after 60 minutes of inactivity.
    
    Args:
        params (dict): Request parameters
        ip_address (str): Client IP address
        
    Returns:
        str: Session ID
    """
    now = datetime.utcnow()
    
    # Check if session_id is provided
    provided_session_id = params.get("session_id")
    
    if provided_session_id:
        # Validate existing session
        if provided_session_id in _active_sessions:
            last_activity = _active_sessions[provided_session_id]
            if now - last_activity < SESSION_TIMEOUT:
                # Session is still active, update last activity
                _active_sessions[provided_session_id] = now
                return provided_session_id
            else:
                # Session expired, create new one
                del _active_sessions[provided_session_id]
    
    # Create new session
    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    _active_sessions[session_id] = now
    
    # Clean up expired sessions periodically
    if len(_active_sessions) > 1000:  # Prevent memory bloat
        expired_sessions = [
            sid for sid, last_activity in _active_sessions.items()
            if now - last_activity >= SESSION_TIMEOUT
        ]
        for sid in expired_sessions:
            del _active_sessions[sid]
    
    return session_id


def get_client_ip():
    """Get client IP address from request."""
    from flask import request
    # Check for forwarded IP (if behind proxy)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'


def process_tracking_event():
    """
    Process and store a tracking event from the request.
    
    Returns:
        dict: Event data dictionary ready for storage
    """
    # Get all parameters (works for both GET and POST)
    if request.method == 'GET':
        params = request.args.to_dict()
    else:
        # POST: try JSON first, then form data, then query string
        if request.is_json:
            params = request.get_json() or {}
        else:
            params = {**request.form.to_dict(), **request.args.to_dict()}
    
    # Validate required UTM parameters
    required_utms = ["utm_source", "utm_medium", "utm_campaign"]
    missing_utms = [utm for utm in required_utms if not params.get(utm)]
    
    if missing_utms:
        raise ValueError(f"Missing required UTM parameters: {', '.join(missing_utms)}")
    
    # Get client information
    ip_address = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    referrer = request.headers.get('Referer', '')
    full_url = request.url
    
    # Generate or get session ID
    session_id = get_or_create_session_id(params, ip_address)
    
    # Detect platform
    platform_detected = detect_platform(params)
    
    # Build event data
    event_data = {
        # Timestamps
        "timestamp": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        
        # UTM Parameters
        "utm_source": params.get("utm_source", ""),
        "utm_medium": params.get("utm_medium", ""),
        "utm_campaign": params.get("utm_campaign", ""),
        "utm_content": params.get("utm_content"),
        "utm_term": params.get("utm_term"),
        
        # Platform IDs
        "campaign_id": params.get("campaign_id"),
        "adset_id": params.get("adset_id"),
        "ad_id": params.get("ad_id"),
        "placement": params.get("placement"),
        "igshid": params.get("igshid") or params.get("igsh"),
        
        # Platform Click IDs
        "gclid": params.get("gclid"),
        "fbclid": params.get("fbclid"),
        "ttclid": params.get("ttclid"),
        "msclkid": params.get("msclkid"),
        
        # System-generated
        "session_id": session_id,
        "referrer_url": referrer or params.get("referrer_url"),
        
        # Request metadata
        "ip_address": ip_address,
        "user_agent": user_agent,
        "full_url": full_url,
        
        # Additional
        "platform_detected": platform_detected,
        
        # Behavioral & Pathway Data
        "event_type": params.get("event_type", "page_view"),
        "current_page": params.get("current_page"),
        "previous_page": params.get("previous_page"),
        "sequence_step": params.get("sequence_step"),
        "element_tag": params.get("element_tag"),
        "element_id": params.get("element_id"),
        "element_class": params.get("element_class"),
        "element_text": params.get("element_text"),
        "target_url": params.get("target_url"),
        
        # Technical Data
        "screen_resolution": params.get("screen_resolution"),
        "language": params.get("language"),
        
        "raw_params": params,  # Store all params as dict for flexibility
        
        # Domain & Host Data (Auto-detected)
        "host": request.host,
        "domain": ".".join(request.host.split(".")[-2:]) if request.host.count(".") > 1 else request.host,
        "subdomain": request.host.split(".")[0] if request.host.count(".") > 1 else "www"
    }

    # Override host/domain/subdomain if 'url' parameter is present (from client-side script)
    if params.get("url"):
        try:
            parsed_url = urlparse(params.get("url"))
            hostname = parsed_url.netloc
            if hostname:
                event_data["host"] = hostname
                event_data["domain"] = ".".join(hostname.split(".")[-2:]) if hostname.count(".") > 1 else hostname
                event_data["subdomain"] = hostname.split(".")[0] if hostname.count(".") > 1 else "www"
        except Exception as e:
            logger.warning(f"Failed to parse URL for host detection: {e}")
    
    # Remove None values to keep database clean
    event_data = {k: v for k, v in event_data.items() if v is not None}
    
    return event_data


def store_event(event_data):
    """
    Store event in MongoDB.
    
    Args:
        event_data (dict): Event data dictionary
        
    Returns:
        str: Inserted document ID
    """
    try:
        doc_id = insert_event(event_data)
        logger.info(f"Event stored: {doc_id}")
        return doc_id
    except Exception as e:
        logger.error(f"Error storing event: {e}")
        raise

