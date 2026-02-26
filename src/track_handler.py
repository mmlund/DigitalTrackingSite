"""
Track handler for processing and storing tracking events.

Phase 1 — Envelope Fields
Every event now includes a standardized "envelope" of top-level fields
(occurred_at, utm.*, source_system, schema_version, visitor_id, etc.)
alongside the original raw_params dict.
"""

import uuid
from datetime import datetime, timedelta
from urllib.parse import urlparse
from flask import request
from .database import insert_event, get_collection
from .config import BASE_URL
import logging

logger = logging.getLogger(__name__)

# Current envelope schema version — bump when envelope shape changes.
SCHEMA_VERSION = 1

# Session management: 60-minute timeout
SESSION_TIMEOUT = timedelta(minutes=60)
_active_sessions = {}  # {session_id: last_activity}

# Known host → site_id mapping for inference
_HOST_SITE_MAP = {
    "booking.dnstrainer.com": "dnstrainer",
    "dnstrainer.com": "dnstrainer",
    "www.dnstrainer.com": "dnstrainer",
    "www.booking.dnstrainer.com": "dnstrainer",
    "booking.scandinavianclinic.com": "scandinavian",
    "scandinavianclinic.com": "scandinavian",
    "www.scandinavianclinic.com": "scandinavian",
    "www.booking.scandinavianclinic.com": "scandinavian",
}


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
    """
    now = datetime.utcnow()
    provided_session_id = params.get("session_id")

    if provided_session_id:
        if provided_session_id in _active_sessions:
            last_activity = _active_sessions[provided_session_id]
            if now - last_activity < SESSION_TIMEOUT:
                _active_sessions[provided_session_id] = now
                return provided_session_id
            else:
                del _active_sessions[provided_session_id]

    session_id = f"sess_{uuid.uuid4().hex[:10]}"
    _active_sessions[session_id] = now

    # Clean up expired sessions periodically
    if len(_active_sessions) > 1000:
        expired = [
            sid for sid, ts in _active_sessions.items()
            if now - ts >= SESSION_TIMEOUT
        ]
        for sid in expired:
            del _active_sessions[sid]

    return session_id


def get_client_ip():
    """Get client IP address from request."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'


# ── Envelope helpers ─────────────────────────────────────────────────

def _parse_occurred_at(params):
    """Parse occurred_at from raw_params.timestamp, falling back to server time."""
    raw_ts = params.get("timestamp")
    if raw_ts:
        try:
            if isinstance(raw_ts, str):
                return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            elif isinstance(raw_ts, datetime):
                return raw_ts
        except (ValueError, TypeError):
            logger.warning(f"Could not parse timestamp '{raw_ts}', using server time")
    return datetime.utcnow()


def _resolve_host_domain(params):
    """
    Determine host, domain, and subdomain from the params URL or the request.
    Returns (host, domain, subdomain).
    """
    host = request.host
    domain = "." .join(host.split(".")[-2:]) if host.count(".") > 1 else host
    subdomain = host.split(".")[0] if host.count(".") > 1 else "www"

    # Override from client-supplied 'url' param if present
    url_param = params.get("url")
    if url_param:
        try:
            parsed = urlparse(url_param)
            hostname = parsed.netloc
            if hostname:
                host = hostname
                domain = ".".join(hostname.split(".")[-2:]) if hostname.count(".") > 1 else hostname
                subdomain = hostname.split(".")[0] if hostname.count(".") > 1 else "www"
        except Exception as e:
            logger.warning(f"Failed to parse URL for host detection: {e}")

    # Normalize: strip www. prefix
    if host.startswith("www."):
        host = host[4:]

    return host, domain, subdomain


def _infer_site_id(params, host):
    """
    Infer site_id. Priority:
      1. Explicit params.site_id
      2. Known host → site_id mapping
      3. "unknown"
    """
    explicit = params.get("site_id")
    if explicit:
        return explicit

    # Try host lookup
    site_id = _HOST_SITE_MAP.get(host)
    if site_id:
        return site_id

    # Try with www. prefix in case it was stripped
    site_id = _HOST_SITE_MAP.get(f"www.{host}")
    if site_id:
        return site_id

    logger.warning(f"Could not infer site_id for host '{host}', defaulting to 'unknown'")
    return "unknown"


def _infer_source_system(params, host, site_id):
    """
    Infer source_system using 3-tier priority:
      1. Booking host or known EA payload fields → easyappointments_<site_id>
      2. utm_source starts with "easyappointments" → use that value
      3. Otherwise → "web"
    """
    # Tier 1: booking host or EA-specific payload
    is_booking_host = host.startswith("booking.") or host.startswith("www.booking.")
    has_ea_payload = bool(params.get("booking_id"))

    if is_booking_host or has_ea_payload:
        return f"easyappointments_{site_id}"

    # Tier 2: utm_source starts with easyappointments
    utm_source = (params.get("utm_source") or "").lower()
    if utm_source.startswith("easyappointments"):
        return params.get("utm_source")

    # Tier 3: default
    return "web"


def _build_utm_object(params):
    """Build the normalized nested utm object."""
    def _or_none(val):
        """Convert empty string to None."""
        return val if val else None

    return {
        "source": _or_none(params.get("utm_source")),
        "medium": _or_none(params.get("utm_medium")),
        "campaign": _or_none(params.get("utm_campaign")),
        "term": _or_none(params.get("utm_term")),
        "content": _or_none(params.get("utm_content")),
    }


# ── Main processing ─────────────────────────────────────────────────

def process_tracking_event():
    """
    Process and store a tracking event from the request.

    Returns:
        dict: Event data dictionary ready for storage, including envelope fields.
    """
    # Get all parameters (works for both GET and POST)
    if request.method == 'GET':
        params = request.args.to_dict()
    else:
        if request.is_json:
            params = request.get_json() or {}
        else:
            params = {**request.form.to_dict(), **request.args.to_dict()}

    # ── Event type: resolve BEFORE UTM validation ──────────────
    event_type = params.get("event_type", "")
    if not event_type:
        event_type = "unknown"
        logger.warning("Event received without event_type, defaulting to 'unknown'")

    # ── Validation for legacy UTM-required events ────────────────
    # Only genuine ad-tracking types require UTM params.
    # "unknown" (from missing event_type) does NOT require UTMs.
    utm_required_types = {"ad_click", "landing"}
    if event_type in utm_required_types:
        required_utms = ["utm_source", "utm_medium", "utm_campaign"]
        missing_utms = [utm for utm in required_utms if not params.get(utm)]
        if missing_utms:
            raise ValueError(f"Missing required UTM parameters: {', '.join(missing_utms)}")

    # ── Client info ──────────────────────────────────────────────
    ip_address = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    referrer_header = request.headers.get('Referer', '')

    session_id = get_or_create_session_id(params, ip_address)
    platform_detected = detect_platform(params)

    # ── Resolve host / domain / subdomain ────────────────────────
    host, domain, subdomain = _resolve_host_domain(params)

    # ── Infer site_id and source_system ──────────────────────────
    site_id = _infer_site_id(params, host)
    source_system = _infer_source_system(params, host, site_id)

    # ── Envelope timestamps ──────────────────────────────────────
    occurred_at = _parse_occurred_at(params)
    server_received_at = datetime.utcnow()

    # ── Build event data ─────────────────────────────────────────
    # Envelope fields are set ONCE here — they must not be overwritten below.
    event_data = {
        # ── ENVELOPE (Phase 1) — single-source-of-truth ──────
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "site_id": site_id,
        "host": host,
        "domain": domain,
        "url": params.get("url"),
        "referrer": params.get("referrer") or referrer_header or None,
        "session_id": session_id,
        "visitor_id": params.get("device_id"),
        "utm": _build_utm_object(params),
        "source_system": source_system,

        # ── Legacy / backward-compat fields ───────────────────
        "timestamp": server_received_at,
        "created_at": server_received_at,
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
        "referrer_url": referrer_header or params.get("referrer_url"),

        # Request metadata
        "ip_address": ip_address,
        "user_agent": user_agent,
        "full_url": request.url,

        # Additional
        "platform_detected": platform_detected,
        "subdomain": subdomain,

        # Behavioral & Pathway Data
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

        # Raw params — preserved unchanged
        "raw_params": params,
    }

    # Promote customer data fields to top-level for easier querying.
    # Guard: never overwrite envelope fields.
    _ENVELOPE_KEYS = {
        "schema_version", "event_type", "occurred_at", "site_id",
        "host", "domain", "url", "referrer", "session_id",
        "visitor_id", "utm", "source_system",
    }
    customer_fields = ['customer_name', 'customer_email', 'customer_phone']
    for field in customer_fields:
        if params.get(field) and field not in _ENVELOPE_KEYS:
            event_data[field] = params[field]

    # Phase 3B: Promote appointment fields to top-level.
    appointment_fields = [
        "appointment_id", "appointment_datetime",
        "cancelled_by", "cancel_reason",
    ]
    for field in appointment_fields:
        if params.get(field) and field not in _ENVELOPE_KEYS:
            event_data[field] = params[field]

    # Normalize appointment_id for booking-related events
    _APPT_EVENT_TYPES = {
        "booking_confirmed", "booking_cancelled", "attended", "no_show", "purchase",
    }
    if event_type in _APPT_EVENT_TYPES and not event_data.get("appointment_id"):
        aid = params.get("booking_id") or params.get("appointment_id")
        if not aid:
            tid = params.get("transaction_id", "")
            if isinstance(tid, str) and tid.startswith("EA-"):
                aid = tid
        if aid:
            event_data["appointment_id"] = str(aid)
        elif event_type == "booking_cancelled":
            # Data Quality Signaling (Phase 3B Hardening)
            logger.warning("booking_cancelled event missing appointment_id — falling back to simple counting")
            # TODO: Exposure a metric: % events missing appointment_id
            # This fallback is transitional until EA hooks are fully hardened.

    # Remove None values from NON-envelope fields to keep database clean.
    # Envelope fields (visitor_id, referrer, url) are allowed to be None/absent.
    envelope_nullable = {"visitor_id", "referrer", "url"}
    event_data = {
        k: v for k, v in event_data.items()
        if v is not None or k in envelope_nullable
    }

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
