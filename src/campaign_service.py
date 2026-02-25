"""
Campaign service layer — business logic for campaign management.

Handles CRUD for campaigns, link generation, spend tracking, asset storage (GridFS),
and auto-date updates from incoming tracking events.
"""

import uuid
import logging
from datetime import datetime
from bson import ObjectId

from .database import (
    get_campaigns_collection,
    get_campaign_links_collection,
    get_campaign_spend_collection,
    get_campaign_assets_collection,
    get_gridfs_bucket,
)
from .url_generator import build_tracking_url

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

VALID_CHANNELS = {"google_ads", "meta", "instagram", "seo", "referral", "email", "other"}
VALID_STATUSES = {"draft", "scheduled", "active", "paused", "ended"}
STATUS_SORT_ORDER = {"active": 0, "scheduled": 1, "draft": 2, "paused": 3, "ended": 4}
VALID_GOALS = {"confirmed_bookings", "awareness"}
VALID_CONVERSION_EVENTS = {"booking_confirmed", "purchase", "engaged_session"}
VALID_SITES = {"scandinavian", "dnstrainer"}

# Fields that become read-only once a campaign is active
LOCKED_TRACKING_FIELDS = {
    "tracking_defaults.utm_campaign_slug",
    "tracking_defaults.utm_source",
    "tracking_defaults.utm_medium",
}


# ── Helpers ──────────────────────────────────────────────────────────

def _now():
    return datetime.utcnow()


def _serialize_doc(doc):
    """Make a MongoDB document JSON-serializable."""
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    for key in ("created_at", "updated_at", "notes_updated_at"):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()
    # Serialize nested dates
    dates = doc.get("dates", {})
    for dk in ("planned_start_date", "actual_start_date", "actual_end_date"):
        if isinstance(dates.get(dk), datetime):
            dates[dk] = dates[dk].isoformat()
    return doc


def _serialize_docs(docs):
    return [_serialize_doc(d) for d in docs]


# ── Campaign CRUD ────────────────────────────────────────────────────

def create_campaign(data):
    """
    Create a new campaign.

    Args:
        data (dict): Campaign data. 'name' is required.

    Returns:
        dict: Created campaign document.

    Raises:
        ValueError: If validation fails.
    """
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Campaign name is required")

    site_id = data.get("site_id", "dnstrainer")
    if site_id not in VALID_SITES:
        raise ValueError(f"site_id must be one of {VALID_SITES}")

    channel = data.get("channel", "other")
    if channel not in VALID_CHANNELS:
        raise ValueError(f"channel must be one of {VALID_CHANNELS}")

    status = data.get("status", "draft")
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")

    # Planning sub-document
    planning_data = data.get("planning", {})
    primary_goal = planning_data.get("primary_goal", "confirmed_bookings")
    if primary_goal not in VALID_GOALS:
        raise ValueError(f"primary_goal must be one of {VALID_GOALS}")

    planning = {
        "rationale": (planning_data.get("rationale") or "").strip(),
        "target_persona": (planning_data.get("target_persona") or "").strip(),
        "target_audience": (planning_data.get("target_audience") or "").strip(),
        "primary_goal": primary_goal,
        "offer": (planning_data.get("offer") or "").strip() or None,
    }

    # Tracking defaults
    td = data.get("tracking_defaults", {})
    utm_source = (td.get("utm_source") or "").strip()
    utm_medium = (td.get("utm_medium") or "").strip()
    utm_campaign_slug = (td.get("utm_campaign_slug") or "").strip()

    if not utm_source:
        raise ValueError("tracking_defaults.utm_source is required")
    if not utm_medium:
        raise ValueError("tracking_defaults.utm_medium is required")
    if not utm_campaign_slug:
        raise ValueError("tracking_defaults.utm_campaign_slug is required")

    expected_event = td.get("expected_conversion_event", "booking_confirmed")
    if expected_event not in VALID_CONVERSION_EVENTS:
        raise ValueError(f"expected_conversion_event must be one of {VALID_CONVERSION_EVENTS}")

    engagement_threshold = None
    if expected_event == "engaged_session":
        engagement_threshold = td.get("engagement_seconds_threshold", 30)
        if not (10 <= engagement_threshold <= 60):
            raise ValueError("engagement_seconds_threshold must be between 10 and 60")

    tracking_defaults = {
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign_slug": utm_campaign_slug,
        "utm_campaign_aliases": td.get("utm_campaign_aliases", []),
        "expected_conversion_event": expected_event,
        "engagement_seconds_threshold": engagement_threshold,
    }

    # Dates
    dates_data = data.get("dates", {})
    planned_start = dates_data.get("planned_start_date")
    if planned_start and isinstance(planned_start, str):
        try:
            planned_start = datetime.fromisoformat(planned_start)
        except ValueError:
            planned_start = None

    dates = {
        "planned_start_date": planned_start,
        "actual_start_date": None,
        "actual_end_date": None,
    }

    # Landing pages
    landing_pages = data.get("landing_pages", [])
    if isinstance(landing_pages, str):
        landing_pages = [lp.strip() for lp in landing_pages.split(",") if lp.strip()]

    now = _now()
    campaign = {
        "campaign_id": str(uuid.uuid4()),
        "site_id": site_id,
        "name": name,
        "channel": channel,
        "status": status,
        "planning": planning,
        "notes": (data.get("notes") or "").strip() or None,
        "notes_updated_at": None,
        "dates": dates,
        "tracking_defaults": tracking_defaults,
        "landing_pages": landing_pages,
        "created_at": now,
        "updated_at": now,
    }

    col = get_campaigns_collection()
    col.insert_one(campaign)
    return _serialize_doc(campaign)


def get_campaign(campaign_id):
    """Fetch a single campaign by campaign_id."""
    col = get_campaigns_collection()
    doc = col.find_one({"campaign_id": campaign_id})
    return _serialize_doc(doc)


def list_campaigns(filters=None, sort_by_status=True):
    """
    List campaigns with optional filters.

    Args:
        filters (dict): Optional MongoDB filter fields (site_id, channel, status).
        sort_by_status (bool): If True, sort by status priority then updated_at desc.

    Returns:
        list[dict]: List of campaign documents.
    """
    col = get_campaigns_collection()
    query = {}

    if filters:
        if filters.get("site_id"):
            query["site_id"] = filters["site_id"]
        if filters.get("channel"):
            query["channel"] = filters["channel"]
        if filters.get("status"):
            query["status"] = filters["status"]

    docs = list(col.find(query))

    if sort_by_status:
        docs.sort(key=lambda d: (
            STATUS_SORT_ORDER.get(d.get("status", "ended"), 99),
            -(d.get("updated_at") or _now()).timestamp(),
        ))

    return _serialize_docs(docs)


def update_campaign(campaign_id, data):
    """
    Partial update of a campaign. Enforces read-only on core tracking fields
    when campaign status is 'active'.

    Args:
        campaign_id (str): Campaign ID.
        data (dict): Fields to update.

    Returns:
        dict: Updated campaign document.

    Raises:
        ValueError: If campaign not found or validation error.
    """
    col = get_campaigns_collection()
    existing = col.find_one({"campaign_id": campaign_id})
    if not existing:
        raise ValueError(f"Campaign {campaign_id} not found")

    is_active = existing.get("status") == "active"

    update_fields = {}
    now = _now()

    # Top-level simple fields
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise ValueError("Campaign name is required")
        update_fields["name"] = name

    if "site_id" in data:
        if data["site_id"] not in VALID_SITES:
            raise ValueError(f"site_id must be one of {VALID_SITES}")
        update_fields["site_id"] = data["site_id"]

    if "channel" in data:
        if data["channel"] not in VALID_CHANNELS:
            raise ValueError(f"channel must be one of {VALID_CHANNELS}")
        update_fields["channel"] = data["channel"]

    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        update_fields["status"] = data["status"]

    # Notes — always editable
    if "notes" in data:
        update_fields["notes"] = (data["notes"] or "").strip() or None
        update_fields["notes_updated_at"] = now

    # Planning — always editable
    if "planning" in data:
        for field in ("rationale", "target_persona", "target_audience", "primary_goal", "offer"):
            if field in data["planning"]:
                if field == "primary_goal" and data["planning"][field] not in VALID_GOALS:
                    raise ValueError(f"primary_goal must be one of {VALID_GOALS}")
                update_fields[f"planning.{field}"] = data["planning"][field]

    # Dates — only planned_start_date is user-editable
    if "dates" in data:
        if "planned_start_date" in data["dates"]:
            psd = data["dates"]["planned_start_date"]
            if psd and isinstance(psd, str):
                try:
                    psd = datetime.fromisoformat(psd)
                except ValueError:
                    psd = None
            update_fields["dates.planned_start_date"] = psd

    # Tracking defaults — some read-only when active
    if "tracking_defaults" in data:
        td = data["tracking_defaults"]
        locked_keys = {"utm_source", "utm_medium", "utm_campaign_slug"}

        for key in locked_keys:
            if key in td and is_active:
                raise ValueError(
                    f"Cannot modify tracking_defaults.{key} while campaign is active"
                )
            if key in td:
                val = (td[key] or "").strip()
                if not val:
                    raise ValueError(f"tracking_defaults.{key} is required")
                update_fields[f"tracking_defaults.{key}"] = val

        # Non-locked tracking fields
        if "utm_campaign_aliases" in td:
            update_fields["tracking_defaults.utm_campaign_aliases"] = td["utm_campaign_aliases"]
        if "expected_conversion_event" in td:
            ev = td["expected_conversion_event"]
            if ev not in VALID_CONVERSION_EVENTS:
                raise ValueError(f"expected_conversion_event must be one of {VALID_CONVERSION_EVENTS}")
            update_fields["tracking_defaults.expected_conversion_event"] = ev
        if "engagement_seconds_threshold" in td:
            thr = td["engagement_seconds_threshold"]
            if thr is not None and not (10 <= thr <= 60):
                raise ValueError("engagement_seconds_threshold must be between 10 and 60")
            update_fields["tracking_defaults.engagement_seconds_threshold"] = thr

    # Landing pages — always editable
    if "landing_pages" in data:
        lps = data["landing_pages"]
        if isinstance(lps, str):
            lps = [lp.strip() for lp in lps.split(",") if lp.strip()]
        update_fields["landing_pages"] = lps

    update_fields["updated_at"] = now

    col.update_one({"campaign_id": campaign_id}, {"$set": update_fields})
    return get_campaign(campaign_id)


def set_campaign_status(campaign_id, status):
    """Quick status change for a campaign."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")

    col = get_campaigns_collection()
    result = col.update_one(
        {"campaign_id": campaign_id},
        {"$set": {"status": status, "updated_at": _now()}}
    )
    if result.matched_count == 0:
        raise ValueError(f"Campaign {campaign_id} not found")
    return get_campaign(campaign_id)


def duplicate_campaign(campaign_id):
    """
    Deep-copy a campaign with a new ID, reset dates, set status=draft.
    """
    col = get_campaigns_collection()
    original = col.find_one({"campaign_id": campaign_id})
    if not original:
        raise ValueError(f"Campaign {campaign_id} not found")

    now = _now()
    new_campaign = dict(original)
    new_campaign.pop("_id", None)
    new_campaign["campaign_id"] = str(uuid.uuid4())
    new_campaign["name"] = f"{original['name']} (copy)"
    new_campaign["status"] = "draft"
    new_campaign["dates"] = {
        "planned_start_date": None,
        "actual_start_date": None,
        "actual_end_date": None,
    }
    new_campaign["created_at"] = now
    new_campaign["updated_at"] = now

    col.insert_one(new_campaign)
    return _serialize_doc(new_campaign)


# ── Campaign Links ───────────────────────────────────────────────────

def generate_campaign_link(campaign_id, link_data):
    """
    Generate a tracking URL for a campaign and save it.

    Link inherits utm_source, utm_medium, utm_campaign from the campaign's
    tracking_defaults. Only utm_content and utm_term are specified per-link.

    Args:
        campaign_id (str): Parent campaign ID.
        link_data (dict): Keys: landing_page, utm_content, utm_term,
                          dynamic_placeholders_enabled, label.

    Returns:
        dict: Created campaign link document.
    """
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    td = campaign["tracking_defaults"]
    landing_page = (link_data.get("landing_page") or "").strip()
    if not landing_page:
        raise ValueError("landing_page is required")

    utm_content = (link_data.get("utm_content") or "").strip() or None
    utm_term = (link_data.get("utm_term") or "").strip() or None
    dynamic = link_data.get("dynamic_placeholders_enabled", False)

    # Build tracking URL using existing url_generator
    generated_url = build_tracking_url(
        utm_source=td["utm_source"],
        utm_medium=td["utm_medium"],
        campaign_name=td["utm_campaign_slug"],
        ad_name=utm_content,
        adset_name=utm_term,
        use_dynamic_placeholders=dynamic,
    )

    # Replace base URL with the landing page
    # The build_tracking_url uses BASE_URL, we need to swap it with the landing page
    from .config import BASE_URL
    if generated_url.startswith(BASE_URL):
        query_part = generated_url[len(BASE_URL):]
        generated_url = landing_page.rstrip("/") + query_part

    now = _now()
    link_doc = {
        "link_id": str(uuid.uuid4()),
        "campaign_id": campaign_id,
        "site_id": campaign["site_id"],
        "landing_page": landing_page,
        "utm": {
            "source": td["utm_source"],
            "medium": td["utm_medium"],
            "campaign": td["utm_campaign_slug"],
            "content": utm_content,
            "term": utm_term,
        },
        "dynamic_placeholders_enabled": dynamic,
        "generated_url": generated_url,
        "label": (link_data.get("label") or "").strip() or None,
        "created_at": now,
        "last_used_at": None,
    }

    col = get_campaign_links_collection()
    col.insert_one(link_doc)
    return _serialize_doc(link_doc)


def list_campaign_links(campaign_id):
    """Return all links for a campaign, newest first."""
    col = get_campaign_links_collection()
    docs = list(col.find({"campaign_id": campaign_id}).sort("created_at", -1))
    return _serialize_docs(docs)


# ── Campaign Spend ───────────────────────────────────────────────────

def upsert_spend(campaign_id, month, amount, currency="USD", source="manual", note=None):
    """
    Insert or update monthly spend for a campaign.

    Args:
        campaign_id (str): Campaign ID.
        month (str): Month in YYYY-MM format.
        amount (float): Spend amount.
        currency (str): Currency code.
        source (str): Source of spend data.
        note (str): Optional note.

    Returns:
        dict: Upserted spend document.
    """
    # Verify campaign exists
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    col = get_campaign_spend_collection()
    now = _now()

    result = col.update_one(
        {"campaign_id": campaign_id, "month": month},
        {
            "$set": {
                "amount": amount,
                "currency": currency,
                "source": source,
                "note": (note or "").strip() or None,
                "updated_at": now,
            },
            "$setOnInsert": {
                "campaign_id": campaign_id,
                "month": month,
            },
        },
        upsert=True,
    )

    doc = col.find_one({"campaign_id": campaign_id, "month": month})
    return _serialize_doc(doc)


def list_spend(campaign_id):
    """Return spend entries for a campaign, sorted by month descending."""
    col = get_campaign_spend_collection()
    docs = list(col.find({"campaign_id": campaign_id}).sort("month", -1))
    return _serialize_docs(docs)


# ── Campaign Assets (GridFS) ────────────────────────────────────────

def save_asset(campaign_id, asset_type, filename=None, file_data=None,
               raw_text=None, content_type="application/octet-stream"):
    """
    Save a campaign asset. Files go to GridFS, text is stored inline.

    Args:
        campaign_id (str): Campaign ID.
        asset_type (str): One of keywords, creative_notes, audience_notes, ad_examples_images.
        filename (str): Original filename (for file uploads).
        file_data (bytes): File content.
        raw_text (str): Text content (for text-based assets).
        content_type (str): MIME type.

    Returns:
        dict: Asset metadata document.
    """
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    storage_key = None
    storage_provider = None

    if file_data:
        # Store file in GridFS
        fs = get_gridfs_bucket()
        file_id = fs.put(
            file_data,
            filename=filename or "unnamed",
            content_type=content_type,
            campaign_id=campaign_id,
        )
        storage_provider = "gridfs"
        storage_key = str(file_id)

    now = _now()
    asset_doc = {
        "asset_id": str(uuid.uuid4()),
        "campaign_id": campaign_id,
        "asset_type": asset_type,
        "filename": filename,
        "storage_provider": storage_provider,
        "storage_key": storage_key,
        "content_type": content_type,
        "raw_text": (raw_text or "").strip() or None,
        "parsed": None,
        "created_at": now,
    }

    col = get_campaign_assets_collection()
    col.insert_one(asset_doc)
    return _serialize_doc(asset_doc)


def list_assets(campaign_id):
    """Return asset metadata for a campaign."""
    col = get_campaign_assets_collection()
    docs = list(col.find({"campaign_id": campaign_id}).sort("created_at", -1))
    return _serialize_docs(docs)


def get_asset_file(asset_id):
    """
    Retrieve a file from GridFS by asset_id.

    Returns:
        tuple: (file_data_bytes, filename, content_type) or None.
    """
    col = get_campaign_assets_collection()
    asset = col.find_one({"asset_id": asset_id})
    if not asset or asset.get("storage_provider") != "gridfs":
        return None

    try:
        fs = get_gridfs_bucket()
        grid_file = fs.get(ObjectId(asset["storage_key"]))
        return (grid_file.read(), asset.get("filename", "download"), asset.get("content_type", "application/octet-stream"))
    except Exception as e:
        logger.error(f"Failed to retrieve GridFS file for asset {asset_id}: {e}")
        return None


# ── Auto-Date Hook (called from track_handler) ──────────────────────

def update_campaign_dates_from_event(utm_campaign_slug, occurred_at=None):
    """
    Atomic update of campaign actual_start_date ($min) and actual_end_date ($max)
    when a tracking event with a matching utm_campaign is received.

    Args:
        utm_campaign_slug (str): The utm_campaign value from the event.
        occurred_at (datetime): When the event occurred.
    """
    if not utm_campaign_slug:
        return

    if occurred_at is None:
        occurred_at = _now()

    col = get_campaigns_collection()
    col.update_many(
        {
            "$or": [
                {"tracking_defaults.utm_campaign_slug": utm_campaign_slug},
                {"tracking_defaults.utm_campaign_aliases": utm_campaign_slug},
            ]
        },
        {
            "$min": {"dates.actual_start_date": occurred_at},
            "$max": {"dates.actual_end_date": occurred_at},
            "$set": {"updated_at": _now()},
        },
    )
