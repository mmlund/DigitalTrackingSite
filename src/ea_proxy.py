"""
EA Appointment Proxy — fetch appointments from both EA instances (Hub + Spoke).

Uses the same EA REST API as Scandremind but synchronous (requests) for Flask.
Both instances are queried and results merged for combined schedule views.

EA API integration exists in both DTS and Scandremind intentionally; keep schemas aligned.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — mirrors Scandremind's env var naming
# ---------------------------------------------------------------------------
_EA_SITES = None


def _get_sites() -> List[Dict]:
    """Lazy-init site configs from environment."""
    global _EA_SITES
    if _EA_SITES is not None:
        return _EA_SITES

    _EA_SITES = []

    hub_url = os.getenv("EA_HUB_BASE_URL", "")
    hub_token = os.getenv("EA_HUB_API_TOKEN", "")
    if hub_url and hub_token:
        _EA_SITES.append({
            "site_id": "dnstrainer",
            "site_label": "DNSTrainer",
            "base_url": hub_url.rstrip("/"),
            "token": hub_token,
        })

    spoke_url = os.getenv("EA_SPOKE_BASE_URL", "")
    spoke_token = os.getenv("EA_SPOKE_API_TOKEN", "")
    if spoke_url and spoke_token:
        _EA_SITES.append({
            "site_id": "scandinavian",
            "site_label": "Scandinavian Clinic",
            "base_url": spoke_url.rstrip("/"),
            "token": spoke_token,
        })

    return _EA_SITES


def _fetch_appointments_from_site(site: Dict, date_str: str) -> List[Dict]:
    """
    Fetch appointments for a specific date from one EA instance.

    Args:
        site: site config dict with base_url, token, site_id, site_label
        date_str: YYYY-MM-DD
    Returns:
        Normalised appointment list.
    """
    url = f"{site['base_url']}/appointments"
    headers = {
        "Authorization": f"Bearer {site['token']}",
        "X-Api-Token": site["token"],
        "Content-Type": "application/json",
    }
    # EA API date range params
    params = {
        "from": f"{date_str} 00:00:00",
        "to": f"{date_str} 23:59:59",
        "length": 100,
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        logger.error("EA API error (%s): %s", site["site_id"], e)
        return []
    except ValueError:
        logger.error("Invalid JSON from EA (%s)", site["site_id"])
        return []

    # Normalise to a flat list
    if isinstance(raw, dict):
        raw = [raw]

    appointments = []
    for appt in raw:
        customer = appt.get("customer") or {}
        service = appt.get("service") or {}

        first = customer.get("first_name", "")
        last = customer.get("last_name", "")
        patient_name = f"{first} {last}".strip() or "Unknown"

        # Payment status — EA may expose 'paid' or we infer from notes/custom
        paid_raw = appt.get("paid")
        if paid_raw is not None:
            paid = bool(paid_raw)
        else:
            # Fallback: check notes for payment info
            notes = (appt.get("notes") or "").lower()
            paid = "paid" in notes or "payment" in notes

        appointments.append({
            "appointment_id": str(appt.get("id", "")),
            "start_datetime": appt.get("start_datetime", ""),
            "end_datetime": appt.get("end_datetime", ""),
            "patient_name": patient_name,
            "patient_first_name": first,
            "patient_last_name": last,
            "service_name": service.get("name", ""),
            "site_id": site["site_id"],
            "site_label": site["site_label"],
            "paid": paid,
        })

    return appointments


def get_appointments_for_date(date_str: str) -> List[Dict]:
    """
    Fetch appointments for a date across ALL configured EA instances.

    Args:
        date_str: YYYY-MM-DD
    Returns:
        Merged list sorted by start_datetime ascending.
    """
    sites = _get_sites()
    if not sites:
        logger.warning("No EA sites configured — returning empty schedule")
        return []

    combined = []
    for site in sites:
        combined.extend(_fetch_appointments_from_site(site, date_str))

    # Sort by start_datetime
    def _sort_key(a):
        try:
            return datetime.fromisoformat(a["start_datetime"])
        except (ValueError, TypeError):
            return datetime.max

    combined.sort(key=_sort_key)
    return combined


def reset_sites():
    """Reset cached site configs — useful for testing."""
    global _EA_SITES
    _EA_SITES = None
