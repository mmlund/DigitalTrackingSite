"""
Health service — Phase 3B Hardening

Tracks event health across both EasyAppointments installations.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# In-memory tracking (simple interim solution)
# {site_id: {event_type: last_seen_timestamp}}
_event_health = {}

def track_last_seen(site_id, event_type):
    """Update last seen timestamp for a site and event type."""
    if not site_id or not event_type:
        return

    if site_id not in _event_health:
        _event_health[site_id] = {}
    
    _event_health[site_id][event_type] = datetime.utcnow().isoformat()

def get_health_summary():
    """Return summary of last seen events per site."""
    return _event_health
