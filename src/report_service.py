"""
Report service — Phase 2B

Produces deterministic, UI-ready JSON aggregates and LLM-ready packets.
Uses envelope fields (occurred_at, event_type, site_id, utm.*, session_id,
visitor_id) for all rollups.

Design choices:
  1. visitor_id-based "new patient" labelled "new_visitor_estimated" +
     estimated_from_visitor_id flag wherever identity-dependent
  2. Revenue kept raw (no cancellation subtraction by session)
  3. Loss heuristic includes loss_trigger_event for future switchability
  4. Spend join uses whole_months method (documented in every economics block)
"""

import logging
from datetime import datetime, timedelta
from .database import (
    get_collection,
    get_campaigns_collection,
    get_campaign_spend_collection,
)
from .campaign_service import get_campaign, list_campaigns

logger = logging.getLogger(__name__)

# ── Schema version — bump when top-level response shape changes ──────
REPORT_SCHEMA_VERSION = 1

# ── Timezone used for all weekly boundaries ──────────────────────────
# All occurred_at values are stored as UTC. Weekly boundaries are computed
# in this timezone so that "week start" is always Monday 00:00 in the
# reporting locale. Change this when the clinic starts caring about a
# different timezone for charts.
REPORT_TIMEZONE = "UTC"

# ── Spend join method ────────────────────────────────────────────────
# whole_months: include the FULL amount of any month that overlaps the
# reporting window.  Prorated is not yet implemented.
SPEND_JOIN_METHOD = "whole_months"


# ── Helpers ──────────────────────────────────────────────────────────


def _now():
    return datetime.utcnow()


def _report_meta():
    """Common metadata envelope included in every report response."""
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "timezone": REPORT_TIMEZONE,
        "week_boundary": "iso_monday",
        "spend_join_method": SPEND_JOIN_METHOD,
    }


def _safe_div(a, b, default=0.0):
    """Safe division — returns *default* when divisor is zero-ish."""
    return round(a / b, 4) if b else default


def _week_bucket(dt):
    """Return ISO-week start (Monday 00:00 in REPORT_TIMEZONE) as YYYY-MM-DD."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def _period_bounds(days):
    """Return (start, end) datetimes for the reporting window."""
    end = _now()
    start = end - timedelta(days=days)
    return start, end


def _months_in_period(start, end):
    """Return list of YYYY-MM strings covering the period."""
    months = set()
    cur = start.replace(day=1)
    while cur <= end:
        months.add(cur.strftime("%Y-%m"))
        # advance to next month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def _spend_in_period(campaign_id, start, end):
    """Sum spend using whole_months method.

    whole_months: include the FULL amount of any campaign_spend entry whose
    YYYY-MM overlaps [start, end].  No proration — if the window includes
    even one day of a month, the full monthly spend is counted.
    """
    col = get_campaign_spend_collection()
    months = _months_in_period(start, end)
    total = 0.0
    for doc in col.find({"campaign_id": campaign_id}):
        if doc.get("month") in months:
            total += float(doc.get("amount", 0))
    return round(total, 2)


def _total_spend_in_period(campaign_ids, start, end):
    """Sum spend across multiple campaigns for the period."""
    col = get_campaign_spend_collection()
    months = _months_in_period(start, end)
    total = 0.0
    for doc in col.find({}):
        if doc.get("campaign_id") in campaign_ids and doc.get("month") in months:
            total += float(doc.get("amount", 0))
    return round(total, 2)


def _get_events_in_window(start, end, extra_filter=None):
    """Fetch raw_events within the occurred_at window."""
    col = get_collection("raw_events")
    query = {"occurred_at": {"$gte": start, "$lte": end}}
    if extra_filter:
        query.update(extra_filter)
    return list(col.find(query))


def _serialize_dt(dt):
    """Convert datetime to ISO string or return as-is."""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt


# ── Overview Report (Section 1) ─────────────────────────────────────


def build_overview_report(days=90, rollup="week"):
    """
    Overview KPIs + weekly time series for all active outreach.

    Returns:
        dict with keys: period, kpi_tiles, weekly_series
    """
    start, end = _period_bounds(days)
    events = _get_events_in_window(start, end)

    # ── Collect active campaign IDs for spend rollup ──
    active_campaigns = list_campaigns(filters={"status": "active"})
    active_ids = {c["campaign_id"] for c in active_campaigns}

    # ── Classify events ──
    purchases = []
    bookings_confirmed = []
    bookings_started = []
    all_visitors = set()
    visitor_first_seen = {}  # visitor_id -> earliest occurred_at

    for ev in events:
        et = ev.get("event_type", "")
        vid = ev.get("visitor_id")
        occ = ev.get("occurred_at")

        if vid:
            all_visitors.add(vid)
            if vid not in visitor_first_seen or (occ and occ < visitor_first_seen[vid]):
                visitor_first_seen[vid] = occ

        if et == "purchase":
            purchases.append(ev)
        elif et == "booking_confirmed":
            bookings_confirmed.append(ev)
        elif et == "booking_started":
            bookings_started.append(ev)

    # ── Revenue (raw — no cancellation subtraction per user tweak #2) ──
    total_revenue = sum(
        float(ev.get("raw_params", {}).get("revenue", 0) or 0)
        for ev in purchases
    )

    # ── New visitors (estimated): visitor_id first seen inside window ──
    new_visitors = set()
    # We need to check if visitor existed BEFORE the window
    col = get_collection("raw_events")
    for vid in all_visitors:
        if vid:
            pre_count = col.count_documents({
                "visitor_id": vid,
                "occurred_at": {"$lt": start},
            })
            if pre_count == 0:
                new_visitors.add(vid)

    # Revenue from new visitors (estimated)
    new_visitor_revenue = sum(
        float(ev.get("raw_params", {}).get("revenue", 0) or 0)
        for ev in purchases
        if ev.get("visitor_id") in new_visitors
    )

    # ── KPI tiles ──
    num_visitors = len(all_visitors) or 0
    num_new_visitors = len(new_visitors) or 0
    num_confirmed = len(bookings_confirmed)
    num_started = len(bookings_started)
    total_spend = _total_spend_in_period(active_ids, start, end)

    kpi_tiles = {
        "total_revenue_all": round(total_revenue, 2),
        "total_revenue_new_visitors_estimated": round(new_visitor_revenue, 2),
        "number_of_visitors": num_visitors,
        "number_of_new_visitors_estimated": num_new_visitors,
        "estimated_from_visitor_id": True,
        "booking_confirmation_rate": (
            _safe_div(num_confirmed, num_started)
            if num_started > 0
            else _safe_div(num_confirmed, num_visitors)
        ),
        "booking_confirmation_rate_basis": (
            "booking_started" if num_started > 0 else "visitors"
        ),
        "appointment_completion_rate": None,  # stub — attended not instrumented
        "appointment_completion_rate_note": "requires attended/no_show events",
        "revenue_per_customer": _safe_div(total_revenue, num_visitors),
        "marketing_cost_per_customer": _safe_div(total_spend, num_visitors),
        "marketing_return_on_new_visitors_estimated": _safe_div(
            new_visitor_revenue - total_spend, total_spend
        ) if total_spend > 0 else None,
        "total_marketing_spend": total_spend,
    }

    # ── Weekly time series ──
    week_rev = {}
    week_new_rev = {}
    week_spend = {}

    for ev in purchases:
        wk = _week_bucket(ev.get("occurred_at", _now()))
        rev = float(ev.get("raw_params", {}).get("revenue", 0) or 0)
        week_rev[wk] = week_rev.get(wk, 0) + rev
        if ev.get("visitor_id") in new_visitors:
            week_new_rev[wk] = week_new_rev.get(wk, 0) + rev

    # Build spend per week from monthly spend (evenly distributed)
    for cid in active_ids:
        spend_col = get_campaign_spend_collection()
        for sdoc in spend_col.find({"campaign_id": cid}):
            month_str = sdoc.get("month", "")
            amt = float(sdoc.get("amount", 0))
            if month_str in _months_in_period(start, end):
                # Distribute monthly spend evenly across ~4 weeks
                try:
                    yr, mo = int(month_str[:4]), int(month_str[5:7])
                    first_day = datetime(yr, mo, 1)
                    wk_start = _week_bucket(first_day)
                    # Simplified: assign to first week of month
                    week_spend[wk_start] = week_spend.get(wk_start, 0) + amt
                except (ValueError, IndexError):
                    pass

    # Merge into sorted series
    all_weeks = sorted(set(list(week_rev.keys()) + list(week_new_rev.keys()) + list(week_spend.keys())))
    weekly_series = [
        {
            "week_start_date": wk,
            "revenue_total": round(week_rev.get(wk, 0), 2),
            "revenue_new_visitors_estimated": round(week_new_rev.get(wk, 0), 2),
            "marketing_spend_total": round(week_spend.get(wk, 0), 2),
        }
        for wk in all_weeks
    ]

    return {
        **_report_meta(),
        "period": {
            "start": _serialize_dt(start),
            "end": _serialize_dt(end),
            "days": days,
        },
        "rollup": rollup,
        "kpi_tiles": kpi_tiles,
        "weekly_series": weekly_series,
    }


# ── Phase 3B: Appointment-linked cancellation helpers ─────────────────


def _cancellation_stats(confirmed_count, campaign_events):
    """
    Compute appointment-linked cancellation metrics from raw events.
    Returns dict with not_cancelled, cancelled, late_cancelled, cancellation_rate,
    late_cancel_rate, and cancelled_by_breakdown.
    """
    confirmed_appt_ids = {
        ev.get("appointment_id") for ev in campaign_events
        if ev.get("event_type") == "booking_confirmed" and ev.get("appointment_id")
    }
    cancel_events = [
        ev for ev in campaign_events
        if ev.get("event_type") == "booking_cancelled"
    ]

    if confirmed_appt_ids:
        # Appointment-linked logic
        cancelled_linked = [
            ev for ev in cancel_events
            if ev.get("appointment_id") in confirmed_appt_ids
        ]
        cancelled_count = len(cancelled_linked)
        late_count = sum(
            1 for ev in cancelled_linked
            if ev.get("cancel_classification") == "late_cancel"
        )
        by_breakdown = {"patient": 0, "admin": 0, "system": 0, "unknown": 0}
        for ev in cancelled_linked:
            who = ev.get("cancelled_by", "unknown")
            by_breakdown[who] = by_breakdown.get(who, 0) + 1
    else:
        # Fallback: simple count (no appointment_id available yet)
        cancelled_count = len(cancel_events)
        late_count = sum(
            1 for ev in cancel_events
            if ev.get("cancel_classification") == "late_cancel"
        )
        by_breakdown = {"patient": 0, "admin": 0, "system": 0, "unknown": 0}
        for ev in cancel_events:
            who = ev.get("cancelled_by", "unknown")
            by_breakdown[who] = by_breakdown.get(who, 0) + 1

    not_cancelled = max(confirmed_count - cancelled_count, 0)
    return {
        "cancelled": cancelled_count,
        "not_cancelled": not_cancelled,
        "late_cancelled": late_count,
        "cancellation_rate": _safe_div(cancelled_count, confirmed_count),
        "late_cancel_rate": _safe_div(late_count, cancelled_count) if cancelled_count else None,
        "cancelled_by_breakdown": by_breakdown,
    }


def _build_onsite_funnel(confirmed, type_counts, campaign_events):
    """Build onsite_funnel dict for funnel report (Section 2)."""
    stats = _cancellation_stats(confirmed, campaign_events)
    return {
        "booking_started": type_counts.get("booking_started", 0),
        "booking_confirmed": confirmed,
        "not_cancelled": stats["not_cancelled"],
        "cancellation_rate": stats["cancellation_rate"],
        "late_cancelled": stats["late_cancelled"],
        "cancelled_by_breakdown": stats["cancelled_by_breakdown"],
        "attended_first_visit": 0,   # stub
        "no_show": 0,                # stub
        "second_visit_count": 0,     # stub
        "third_visit_count": 0,      # stub
        "_stubs_note": "attended/no_show/visit_counts require instrumentation",
    }


def _build_booking_funnel(confirmed, cancelled_count_simple, type_counts, campaign_events):
    """Build booking_funnel dict for campaign packet."""
    stats = _cancellation_stats(confirmed, campaign_events)
    return {
        "started_booking": type_counts.get("booking_started", 0),
        "confirmed": confirmed,
        "cancelled": stats["cancelled"],
        "not_cancelled": stats["not_cancelled"],
        "late_cancelled": stats["late_cancelled"],
        "cancelled_by_breakdown": stats["cancelled_by_breakdown"],
        "attended_1_visit": 0,       # stub
        "attended_2_visits": 0,
        "attended_3_visits": 0,
        "attended_4plus_visits": 0,
        "_stubs_note": "attended/visit counts require event instrumentation",
    }


def _build_quality_metrics(confirmed, campaign_events):
    """Build quality dict for campaign packet."""
    stats = _cancellation_stats(confirmed, campaign_events)
    return {
        "cancellation_rate": stats["cancellation_rate"],
        "late_cancel_rate": stats["late_cancel_rate"],
        "no_show_rate": None,  # stub
    }


# ── Funnel Comparison Report (Section 2) ─────────────────────────────


def build_funnel_report(days=90, scope="active_only", group_by="campaign"):
    """
    Per-campaign funnel objects for active campaigns.

    Returns:
        dict with keys: period, scope, group_by, funnels
    """
    start, end = _period_bounds(days)
    events = _get_events_in_window(start, end)

    # Get campaigns
    status_filter = {"status": "active"} if scope == "active_only" else {}
    campaigns = list_campaigns(filters=status_filter)

    # Build slug → campaign mapping
    slug_to_campaigns = {}
    for c in campaigns:
        td = c.get("tracking_defaults", {})
        slug = td.get("utm_campaign_slug")
        if slug:
            slug_to_campaigns[slug] = c
            for alias in td.get("utm_campaign_aliases", []):
                if alias:
                    slug_to_campaigns[alias] = c

    # Group events by campaign
    campaign_events = {}  # campaign_id -> [events]
    for ev in events:
        utm = ev.get("utm", {})
        if not isinstance(utm, dict):
            continue
        camp_slug = utm.get("campaign")
        if camp_slug and camp_slug in slug_to_campaigns:
            cid = slug_to_campaigns[camp_slug]["campaign_id"]
            campaign_events.setdefault(cid, []).append(ev)

    # Build funnel for each campaign
    funnels = []
    for c in campaigns:
        cid = c["campaign_id"]
        cevs = campaign_events.get(cid, [])

        # Count by event_type
        type_counts = {}
        all_sessions = set()     # every session touching this campaign
        landing_sessions = set()  # sessions where utm.campaign matched on landing
        scroll_depths = []
        session_times = {}  # session_id -> {min_at, max_at, landing_url}

        for ev in cevs:
            et = ev.get("event_type", "")
            type_counts[et] = type_counts.get(et, 0) + 1

            sid = ev.get("session_id")
            occ = ev.get("occurred_at")
            url = ev.get("url")

            if sid:
                all_sessions.add(sid)
                # A session is a "landing session" if the UTM campaign param
                # was present on its events (which it always is for cevs,
                # but we track it distinctly for clarity).
                landing_sessions.add(sid)
                if sid not in session_times:
                    session_times[sid] = {"min": occ, "max": occ, "url": url}
                else:
                    if occ:
                        if session_times[sid]["min"] is None or occ < session_times[sid]["min"]:
                            session_times[sid]["min"] = occ
                        if session_times[sid]["max"] is None or occ > session_times[sid]["max"]:
                            session_times[sid]["max"] = occ

            if et == "scroll" and ev.get("raw_params", {}).get("scroll_depth"):
                try:
                    scroll_depths.append(float(ev["raw_params"]["scroll_depth"]))
                except (ValueError, TypeError):
                    pass

        # Avg time on landing (seconds)
        session_durations = []
        for stl in session_times.values():
            if stl["min"] and stl["max"] and stl["min"] != stl["max"]:
                dur = (stl["max"] - stl["min"]).total_seconds()
                if 0 < dur < 7200:  # sanity cap: 2 hours
                    session_durations.append(dur)

        avg_time = _safe_div(sum(session_durations), len(session_durations)) if session_durations else 0
        avg_scroll = _safe_div(sum(scroll_depths), len(scroll_depths)) if scroll_depths else 0

        # Spend & revenue
        spend = _spend_in_period(cid, start, end)
        revenue = sum(
            float(ev.get("raw_params", {}).get("revenue", 0) or 0)
            for ev in cevs if ev.get("event_type") == "purchase"
        )
        confirmed = type_counts.get("booking_confirmed", 0)

        # Ratings (from therapist_ratings collection, joined by date range)
        therapist_avg, patient_avg = _get_ratings_for_period(start, end, c.get("site_id"))

        funnel_obj = {
            "identifiers": {
                "site_id": c.get("site_id"),
                "channel": c.get("channel"),
                "campaign_id": cid,
                "campaign_name": c.get("name"),
                "utm_campaign_slug": c.get("tracking_defaults", {}).get("utm_campaign_slug"),
            },
            "top_of_funnel": {
                "impressions": {"value": 0, "source": "unavailable"},
                "ad_clicks": {"value": 0, "source": "unavailable"},
                "landing_sessions": len(landing_sessions),
                "sessions_total": len(all_sessions),
            },
            "onsite_funnel": _build_onsite_funnel(confirmed, type_counts, cevs),
            "onsite_behavior": {
                "avg_time_on_landing_page_seconds": round(avg_time, 1),
                "avg_scroll_depth": round(avg_scroll, 1),
            },
            "economics": {
                "spend_period": spend,
                "revenue_period": round(revenue, 2),
                "roi_simple": _safe_div(revenue - spend, spend) if spend > 0 else None,
                "cost_per_confirmed_booking": _safe_div(spend, confirmed),
                "cost_per_attended_first_visit": None,  # stub
                "spend_join_method": SPEND_JOIN_METHOD,
            },
            "ratings": {
                "therapist_rating_avg": therapist_avg,
                "patient_rating_avg": patient_avg,
            },
        }
        funnels.append(funnel_obj)

    return {
        **_report_meta(),
        "period": {"start": _serialize_dt(start), "end": _serialize_dt(end), "days": days},
        "scope": scope,
        "group_by": group_by,
        "funnels": funnels,
    }


def _get_ratings_for_period(start, end, site_id=None):
    """
    Get avg therapist and patient ratings within the period.
    Returns (therapist_avg_dict, patient_avg_dict).
    """
    try:
        col = get_collection("therapist_ratings")
        query = {
            "created_at": {"$gte": start, "$lte": end},
        }
        ratings = list(col.find(query))
    except Exception:
        ratings = []

    therapist_vals = []
    patient_vals = []
    for r in ratings:
        val = r.get("rating")
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue
        if r.get("patient_id"):
            patient_vals.append(val)
        else:
            therapist_vals.append(val)

    t_avg = {"value": round(sum(therapist_vals) / len(therapist_vals), 2) if therapist_vals else None,
             "n": len(therapist_vals)}
    p_avg = {"value": round(sum(patient_vals) / len(patient_vals), 2) if patient_vals else None,
             "n": len(patient_vals)}
    return t_avg, p_avg


# ── Value / Long-term Report (Section 3) ────────────────────────────


def build_value_report(days=90):
    """
    Long-term value analysis: ratings trends, new vs repeat revenue,
    LTV (phase-gated), loss analysis, touchpoints.

    Returns:
        dict with keys: period, ratings_trends, new_vs_repeat_revenue,
                        ltv_by_rating, loss_after_booking_page, touchpoints
    """
    start, end = _period_bounds(days)
    events = _get_events_in_window(start, end)

    # ── 1) Ratings trends (weekly) ──
    ratings_trends = _build_ratings_trends(start, end)

    # ── 2) New vs repeat revenue (weekly) ──
    new_vs_repeat = _build_new_vs_repeat_revenue(events, start)

    # ── 3) LTV by rating — phase-gated ──
    ltv_by_rating = {
        "status": "not_available",
        "prerequisites": ["customer_key_hash", "identity_linking"],
        "schema_preview": {
            "by_therapist_rating": [
                {"rating": i, "avg_ltv": None, "n": 0} for i in range(1, 6)
            ],
            "by_patient_rating": [
                {"rating": i, "avg_ltv": None, "n": 0} for i in range(1, 6)
            ],
        },
    }

    # ── 4) Where visitors are lost after viewing booking page ──
    loss_analysis = _build_loss_analysis(events, start, end)

    # ── 5) Touchpoints before first booking ──
    touchpoints = _build_touchpoints(events, start)

    return {
        **_report_meta(),
        "period": {"start": _serialize_dt(start), "end": _serialize_dt(end), "days": days},
        "ratings_trends": ratings_trends,
        "new_vs_repeat_revenue": {
            "estimated_from_visitor_id": True,
            "series": new_vs_repeat,
        },
        "ltv_by_rating": ltv_by_rating,
        "loss_after_booking_page": loss_analysis,
        "touchpoints_before_booking": touchpoints,
    }


def _build_ratings_trends(start, end):
    """Weekly avg therapist/patient ratings + low-rating count."""
    try:
        col = get_collection("therapist_ratings")
        ratings = list(col.find({"created_at": {"$gte": start, "$lte": end}}))
    except Exception:
        ratings = []

    weekly = {}
    for r in ratings:
        wk = _week_bucket(r.get("created_at", _now()))
        if wk not in weekly:
            weekly[wk] = {"therapist": [], "patient": [], "low": 0}
        val = r.get("rating")
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue
        if r.get("patient_id"):
            weekly[wk]["patient"].append(val)
        else:
            weekly[wk]["therapist"].append(val)
        if val < 3:
            weekly[wk]["low"] += 1

    series = []
    for wk in sorted(weekly.keys()):
        d = weekly[wk]
        series.append({
            "week_start_date": wk,
            "therapist_rating_avg": round(sum(d["therapist"]) / len(d["therapist"]), 2) if d["therapist"] else None,
            "patient_rating_avg": round(sum(d["patient"]) / len(d["patient"]), 2) if d["patient"] else None,
            "low_rating_count": d["low"],
        })
    return series


def _build_new_vs_repeat_revenue(events, period_start):
    """Weekly revenue split by new vs repeat visitor (estimated)."""
    # Identify new visitors: first seen within window
    col = get_collection("raw_events")
    visitor_ids = set(ev.get("visitor_id") for ev in events if ev.get("visitor_id"))

    new_visitors = set()
    for vid in visitor_ids:
        pre = col.count_documents({"visitor_id": vid, "occurred_at": {"$lt": period_start}})
        if pre == 0:
            new_visitors.add(vid)

    weekly = {}
    for ev in events:
        if ev.get("event_type") != "purchase":
            continue
        rev = float(ev.get("raw_params", {}).get("revenue", 0) or 0)
        wk = _week_bucket(ev.get("occurred_at", _now()))
        if wk not in weekly:
            weekly[wk] = {"new_visitor_estimated": 0, "repeat_visitor": 0}
        if ev.get("visitor_id") in new_visitors:
            weekly[wk]["new_visitor_estimated"] += rev
        else:
            weekly[wk]["repeat_visitor"] += rev

    return [
        {
            "week_start_date": wk,
            "revenue_new_visitor_estimated": round(weekly[wk]["new_visitor_estimated"], 2),
            "revenue_repeat_visitor": round(weekly[wk]["repeat_visitor"], 2),
        }
        for wk in sorted(weekly.keys())
    ]


def _build_loss_analysis(events, start, end):
    """
    Where visitors are lost after viewing a booking-related page.

    Uses page_view on booking URLs as the trigger event. Includes
    loss_trigger_event field so the trigger can be switched to
    booking_click or booking_started later.
    """
    LOSS_TRIGGER_EVENT = "page_view"
    BOOKING_URL_KEYWORDS = ["book", "appointment", "schedule", "termin"]

    # Group events by session
    sessions = {}
    for ev in events:
        sid = ev.get("session_id")
        if not sid:
            continue
        sessions.setdefault(sid, []).append(ev)

    # Sort each session by occurred_at
    for sid in sessions:
        sessions[sid].sort(key=lambda e: e.get("occurred_at") or _now())

    # Find sessions that viewed a booking page but never confirmed
    lost_sessions = []
    confirmed_sessions = set()

    for sid, sevs in sessions.items():
        has_booking_view = False
        has_confirmed = False
        for ev in sevs:
            et = ev.get("event_type", "")
            url = (ev.get("url") or "").lower()
            if et == LOSS_TRIGGER_EVENT and any(kw in url for kw in BOOKING_URL_KEYWORDS):
                has_booking_view = True
            if et == "booking_confirmed":
                has_confirmed = True
                confirmed_sessions.add(sid)
        if has_booking_view and not has_confirmed:
            lost_sessions.append(sevs)

    # Analyze lost sessions: last event type, last url, time to drop
    last_event_type_counts = {}
    last_url_counts = {}
    time_buckets = {"0-5min": 0, "5-30min": 0, "30min-1h": 0, "1h+": 0}

    for sevs in lost_sessions:
        last_ev = sevs[-1]
        let = last_ev.get("event_type", "unknown")
        last_event_type_counts[let] = last_event_type_counts.get(let, 0) + 1
        lurl = last_ev.get("url", "unknown")
        last_url_counts[lurl] = last_url_counts.get(lurl, 0) + 1

        # Time from first booking-page view to last event
        booking_view_time = None
        for ev in sevs:
            url = (ev.get("url") or "").lower()
            if ev.get("event_type") == LOSS_TRIGGER_EVENT and any(kw in url for kw in BOOKING_URL_KEYWORDS):
                booking_view_time = ev.get("occurred_at")
                break
        if booking_view_time and last_ev.get("occurred_at"):
            delta = (last_ev["occurred_at"] - booking_view_time).total_seconds()
            if delta < 300:
                time_buckets["0-5min"] += 1
            elif delta < 1800:
                time_buckets["5-30min"] += 1
            elif delta < 3600:
                time_buckets["30min-1h"] += 1
            else:
                time_buckets["1h+"] += 1

    # Top 10 last URLs
    top_urls = sorted(last_url_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "loss_trigger_event": LOSS_TRIGGER_EVENT,
        "loss_trigger_note": "Currently uses page_view on booking URLs. Switch to booking_click or booking_started when instrumented.",
        "booking_url_keywords": BOOKING_URL_KEYWORDS,
        "total_sessions_with_trigger": len(lost_sessions) + len(confirmed_sessions),
        "sessions_lost": len(lost_sessions),
        "sessions_confirmed": len(confirmed_sessions),
        "loss_rate": _safe_div(
            len(lost_sessions),
            len(lost_sessions) + len(confirmed_sessions),
        ),
        "last_event_type_distribution": last_event_type_counts,
        "top_last_urls": [{"url": u, "count": c} for u, c in top_urls],
        "time_to_dropoff_buckets": time_buckets,
    }


def _build_touchpoints(events, period_start):
    """
    Average touchpoints (events) before first booking_confirmed per visitor.
    Distribution: 0, 1, 2, 3+ touchpoints.
    Time to booking and time to first visit (stub).
    """
    # Group events by visitor_id
    visitor_events = {}
    for ev in events:
        vid = ev.get("visitor_id")
        if not vid:
            continue
        visitor_events.setdefault(vid, []).append(ev)

    # Sort
    for vid in visitor_events:
        visitor_events[vid].sort(key=lambda e: e.get("occurred_at") or _now())

    touchpoint_counts = []
    time_to_booking = []

    for vid, vevs in visitor_events.items():
        first_booking_idx = None
        for i, ev in enumerate(vevs):
            if ev.get("event_type") == "booking_confirmed":
                first_booking_idx = i
                break
        if first_booking_idx is not None and first_booking_idx > 0:
            touchpoint_counts.append(first_booking_idx)
            first_touch = vevs[0].get("occurred_at")
            booking_time = vevs[first_booking_idx].get("occurred_at")
            if first_touch and booking_time:
                gap = (booking_time - first_touch).total_seconds()
                time_to_booking.append(gap)

    # Distribution
    dist = {"0": 0, "1": 0, "2": 0, "3+": 0}
    for tc in touchpoint_counts:
        if tc == 0:
            dist["0"] += 1
        elif tc == 1:
            dist["1"] += 1
        elif tc == 2:
            dist["2"] += 1
        else:
            dist["3+"] += 1

    avg_touchpoints = _safe_div(sum(touchpoint_counts), len(touchpoint_counts)) if touchpoint_counts else 0
    avg_time_to_booking_hours = _safe_div(
        sum(time_to_booking), len(time_to_booking) * 3600
    ) if time_to_booking else None

    return {
        "visitors_with_booking": len(touchpoint_counts),
        "avg_touchpoints_before_booking": round(avg_touchpoints, 1),
        "touchpoint_distribution": dist,
        "avg_time_to_booking_hours": round(avg_time_to_booking_hours, 1) if avg_time_to_booking_hours else None,
        "avg_time_to_first_visit_hours": None,  # stub — requires attended event
        "_stub_note": "time_to_first_visit requires attended event instrumentation",
    }


# ── Campaign LLM Packet (Section E) ─────────────────────────────────


def build_campaign_packet(campaign_id, days=90):
    """
    Per-campaign report packet for LLM ingestion.

    Includes plan snapshot, funnel, economics, quality, weekly mini-series,
    loss metrics, touchpoints, and redacted example paths.
    """
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    start, end = _period_bounds(days)

    # Get events matching this campaign's UTM slug
    td = campaign.get("tracking_defaults", {})
    slugs = [td.get("utm_campaign_slug")] + (td.get("utm_campaign_aliases") or [])
    slugs = [s for s in slugs if s]

    all_events = _get_events_in_window(start, end)
    campaign_events = [
        ev for ev in all_events
        if isinstance(ev.get("utm"), dict) and ev["utm"].get("campaign") in slugs
    ]

    # Counts
    type_counts = {}
    sessions = set()
    for ev in campaign_events:
        et = ev.get("event_type", "")
        type_counts[et] = type_counts.get(et, 0) + 1
        if ev.get("session_id"):
            sessions.add(ev["session_id"])

    confirmed = type_counts.get("booking_confirmed", 0)
    cancelled = type_counts.get("booking_cancelled", 0)
    revenue = sum(
        float(ev.get("raw_params", {}).get("revenue", 0) or 0)
        for ev in campaign_events if ev.get("event_type") == "purchase"
    )
    spend = _spend_in_period(campaign_id, start, end)

    # Ratings
    therapist_avg, patient_avg = _get_ratings_for_period(start, end, campaign.get("site_id"))

    # Session time approx
    session_times = {}
    scroll_depths = []
    for ev in campaign_events:
        sid = ev.get("session_id")
        occ = ev.get("occurred_at")
        if sid and occ:
            if sid not in session_times:
                session_times[sid] = {"min": occ, "max": occ}
            else:
                if occ < session_times[sid]["min"]:
                    session_times[sid]["min"] = occ
                if occ > session_times[sid]["max"]:
                    session_times[sid]["max"] = occ
        if ev.get("event_type") == "scroll" and ev.get("raw_params", {}).get("scroll_depth"):
            try:
                scroll_depths.append(float(ev["raw_params"]["scroll_depth"]))
            except (ValueError, TypeError):
                pass

    durations = []
    for st in session_times.values():
        d = (st["max"] - st["min"]).total_seconds()
        if 0 < d < 7200:
            durations.append(d)

    avg_time = _safe_div(sum(durations), len(durations)) if durations else 0
    avg_scroll = _safe_div(sum(scroll_depths), len(scroll_depths)) if scroll_depths else 0

    # ── Weekly mini-series ──
    weekly = {}
    for ev in campaign_events:
        wk = _week_bucket(ev.get("occurred_at", _now()))
        if wk not in weekly:
            weekly[wk] = {"bookings": 0, "revenue": 0}
        if ev.get("event_type") == "booking_confirmed":
            weekly[wk]["bookings"] += 1
        if ev.get("event_type") == "purchase":
            weekly[wk]["revenue"] += float(ev.get("raw_params", {}).get("revenue", 0) or 0)

    weekly_series = [
        {
            "week_start_date": wk,
            "bookings": weekly[wk]["bookings"],
            "revenue": round(weekly[wk]["revenue"], 2),
            "spend": 0,  # simplified — monthly spend not split per week here
        }
        for wk in sorted(weekly.keys())
    ]

    # ── Loss metrics for this campaign ──
    loss = _build_loss_analysis(campaign_events, start, end)

    # ── Touchpoints for this campaign ──
    tps = _build_touchpoints(campaign_events, start)

    # ── Redacted example paths (up to 10) ──
    PII_FIELDS = {"customer_name", "customer_email", "customer_phone", "ip_address"}
    example_sessions = list(sessions)[:10]
    example_paths = []
    for sid in example_sessions:
        sevs = sorted(
            [ev for ev in campaign_events if ev.get("session_id") == sid],
            key=lambda e: e.get("occurred_at") or _now()
        )
        path = []
        for ev in sevs:
            step = {
                "event_type": ev.get("event_type"),
                "url": ev.get("url"),
                "occurred_at": _serialize_dt(ev.get("occurred_at")),
            }
            path.append(step)
        example_paths.append({"session_id": sid, "steps": path})

    # ── Build packet ──
    planning = campaign.get("planning", {})
    packet = {
        **_report_meta(),
        "campaign_id": campaign_id,
        "campaign_name": campaign.get("name"),
        "site_id": campaign.get("site_id"),
        "channel": campaign.get("channel"),
        "status": campaign.get("status"),
        "period": {"start": _serialize_dt(start), "end": _serialize_dt(end), "days": days},

        "plan_snapshot": {
            "rationale": planning.get("rationale"),
            "target_persona": planning.get("target_persona"),
            "target_audience": planning.get("target_audience"),
            "primary_goal": planning.get("primary_goal"),
            "offer": planning.get("offer"),
            "notes": campaign.get("notes"),
        },

        "top_of_funnel": {
            "impressions": {"value": 0, "source": "unavailable"},
            "ad_clicks": {"value": 0, "source": "unavailable"},
            "landing_sessions": len(sessions),
            "sessions_total": len(sessions),
        },

        "booking_funnel": _build_booking_funnel(confirmed, cancelled, type_counts, campaign_events),

        "behavior": {
            "avg_time_on_landing_seconds": round(avg_time, 1),
            "avg_scroll_depth": round(avg_scroll, 1),
        },

        "ratings": {
            "therapist_avg": therapist_avg,
            "patient_avg": patient_avg,
        },

        "economics": {
            "total_cost": spend,
            "total_revenue": round(revenue, 2),
            "roi": _safe_div(revenue - spend, spend) if spend > 0 else None,
            "roas": _safe_div(revenue, spend) if spend > 0 else None,
            "cost_per_confirmed": _safe_div(spend, confirmed),
            "cost_per_attended_first": None,  # stub
            "spend_join_method": SPEND_JOIN_METHOD,
        },

        "quality": _build_quality_metrics(confirmed, campaign_events),

        "weekly_series": weekly_series,
        "loss_after_booking_page": loss,
        "touchpoints": tps,
        "example_paths": example_paths,
    }

    return packet
