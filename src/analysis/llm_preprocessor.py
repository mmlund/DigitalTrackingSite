"""
LLM Preprocessor — Phase 1

Aggregates raw_events into summarised JSON for LLM context windows.
Uses the Phase 1 envelope fields (occurred_at, utm.*, site_id, etc.)
so metrics are accurate and site-separated.
"""

import json
from datetime import datetime, timedelta
from ..database import get_collection
import logging

logger = logging.getLogger(__name__)


def _date_filter(days):
    """Build a $match stage for the last N days using occurred_at."""
    start = datetime.utcnow() - timedelta(days=days)
    return {"$match": {"occurred_at": {"$gte": start}}}


# ── Pipeline 1: by_site ──────────────────────────────────────────────

def aggregate_by_site(days=30):
    """
    Per-site summary: sessions, page views, bookings, cancellations,
    purchases, and revenue.
    """
    collection = get_collection("raw_events")

    pipeline = [
        _date_filter(days),
        {
            "$group": {
                "_id": "$site_id",
                "total_events": {"$sum": 1},
                "unique_sessions": {"$addToSet": "$session_id"},
                "page_views": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "page_view"]}, 1, 0]}
                },
                "scrolls": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "scroll"]}, 1, 0]}
                },
                "step_views": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "step_view"]}, 1, 0]}
                },
                "bookings_confirmed": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "booking_confirmed"]}, 1, 0]}
                },
                "bookings_cancelled": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "booking_cancelled"]}, 1, 0]}
                },
                "purchases": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "purchase"]}, 1, 0]}
                },
                "revenue": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$event_type", "purchase"]},
                            {"$ifNull": [{"$toDouble": "$raw_params.revenue"}, 0]},
                            0
                        ]
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "site_id": "$_id",
                "total_events": 1,
                "total_sessions": {"$size": "$unique_sessions"},
                "page_views": 1,
                "scrolls": 1,
                "step_views": 1,
                "bookings_confirmed": 1,
                "bookings_cancelled": 1,
                "purchases": 1,
                "revenue": 1,
            }
        },
        {"$sort": {"total_events": -1}},
    ]

    return list(collection.aggregate(pipeline))


# ── Pipeline 2: by_channel ───────────────────────────────────────────

def aggregate_by_channel(days=30):
    """
    Per-channel breakdown (site × source × medium × campaign).
    Shows clicks, bookings, conversion rate, and revenue.
    """
    collection = get_collection("raw_events")

    pipeline = [
        _date_filter(days),
        {
            "$group": {
                "_id": {
                    "site_id": "$site_id",
                    "source": {"$ifNull": ["$utm.source", "unknown"]},
                    "medium": {"$ifNull": ["$utm.medium", "unknown"]},
                    "campaign": {"$ifNull": ["$utm.campaign", "unknown"]},
                },
                "clicks": {"$sum": 1},
                "bookings_confirmed": {
                    "$sum": {"$cond": [
                        {"$in": ["$event_type", ["booking_confirmed", "purchase"]]},
                        1, 0
                    ]}
                },
                "revenue": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$event_type", "purchase"]},
                            {"$ifNull": [{"$toDouble": "$raw_params.revenue"}, 0]},
                            0
                        ]
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "site_id": "$_id.site_id",
                "source": "$_id.source",
                "medium": "$_id.medium",
                "campaign": "$_id.campaign",
                "clicks": 1,
                "bookings_confirmed": 1,
                "conversion_rate": {
                    "$cond": [
                        {"$eq": ["$clicks", 0]},
                        0,
                        {"$divide": ["$bookings_confirmed", "$clicks"]}
                    ]
                },
                "revenue": 1,
            }
        },
        {"$sort": {"revenue": -1, "bookings_confirmed": -1}},
    ]

    return list(collection.aggregate(pipeline))


# ── Pipeline 3: behavior_summary ─────────────────────────────────────

def aggregate_behavior(days=30):
    """Global behavior counts across all sites."""
    collection = get_collection("raw_events")

    pipeline = [
        _date_filter(days),
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]

    results = list(collection.aggregate(pipeline))
    return {r["_id"]: r["count"] for r in results}


# ── Export ────────────────────────────────────────────────────────────

def export_for_llm(output_file="data/llm_analysis_input.json", days=30):
    """
    Produce the full LLM-ready JSON summary and write it to disk.

    Output schema:
        {
            "analysis_date": str,
            "period_days": int,
            "by_site": [...],
            "by_channel": [...],
            "behavior_summary": {...}
        }
    """
    by_site = aggregate_by_site(days)
    by_channel = aggregate_by_channel(days)
    behavior = aggregate_behavior(days)

    summary = {
        "analysis_date": datetime.utcnow().isoformat(),
        "period_days": days,
        "by_site": by_site,
        "by_channel": by_channel,
        "behavior_summary": behavior,
    }

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"LLM analysis export written to {output_file}")
    return summary
