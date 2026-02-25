"""
Tests for Phase 2B report endpoints.

Verifies:
  - Overview KPIs + weekly time series
  - Funnel comparison (active-only filter, correct counts)
  - Value report (ratings, new vs repeat, loss, touchpoints)
  - Campaign LLM packet (plan context, no PII)
  - Spend joins by campaign_id + month overlap
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app
from src.database import get_collection, get_campaigns_collection, get_campaign_spend_collection


class TestReportsBase(unittest.TestCase):
    """Shared setup: seed events, campaigns, spend, ratings."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        self.now = datetime.utcnow()
        self.two_weeks_ago = self.now - timedelta(days=14)
        self.one_week_ago = self.now - timedelta(days=7)
        self.six_months_ago = self.now - timedelta(days=180)

        with self.app.app_context():
            # Clean collections
            for name in ["raw_events", "campaigns", "campaign_spend", "therapist_ratings"]:
                col = get_collection(name)
                try:
                    col.delete_many({})
                except AttributeError:
                    # If delete_many not available, clear data directly
                    if hasattr(col, 'db') and hasattr(col.db, 'data'):
                        col.db.data[name] = []

            # ── Seed a campaign ──
            campaigns_col = get_campaigns_collection()
            self.campaign_id = "camp-test-001"
            campaigns_col.insert_one({
                "campaign_id": self.campaign_id,
                "name": "Test Google Ads Campaign",
                "site_id": "scandinavian",
                "channel": "google_ads",
                "status": "active",
                "tracking_defaults": {
                    "utm_campaign_slug": "spring-ads-2026",
                    "utm_source": "google",
                    "utm_medium": "cpc",
                },
                "planning": {
                    "rationale": "Drive bookings",
                    "target_persona": "Adults 25-45",
                    "target_audience": "Local area",
                    "primary_goal": "bookings",
                    "offer": "Free consultation",
                },
                "notes": "Test campaign notes",
                "created_at": self.two_weeks_ago,
                "updated_at": self.one_week_ago,
            })

            # ── Seed an inactive campaign (should be excluded from active funnels) ──
            campaigns_col.insert_one({
                "campaign_id": "camp-inactive-001",
                "name": "Old Campaign",
                "site_id": "scandinavian",
                "channel": "meta",
                "status": "ended",
                "tracking_defaults": {
                    "utm_campaign_slug": "old-meta-2025",
                    "utm_source": "facebook",
                    "utm_medium": "paid",
                },
                "created_at": self.six_months_ago,
                "updated_at": self.six_months_ago,
            })

            # ── Seed spend ──
            spend_col = get_campaign_spend_collection()
            current_month = self.now.strftime("%Y-%m")
            spend_col.insert_one({
                "campaign_id": self.campaign_id,
                "month": current_month,
                "amount": 1500.00,
                "currency": "USD",
            })

            # ── Seed events ──
            raw = get_collection("raw_events")

            # New visitor (first seen in period)
            self.new_visitor_id = "visitor-new-001"
            # Returning visitor (has pre-period events)
            self.return_visitor_id = "visitor-return-001"

            # Pre-period event for returning visitor
            raw.insert_one({
                "event_type": "page_view",
                "occurred_at": self.six_months_ago,
                "site_id": "scandinavian",
                "session_id": "sess-old-001",
                "visitor_id": self.return_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/",
                "raw_params": {},
            })

            # New visitor: page_view on booking page
            raw.insert_one({
                "event_type": "page_view",
                "occurred_at": self.two_weeks_ago,
                "site_id": "scandinavian",
                "session_id": "sess-new-001",
                "visitor_id": self.new_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/booking",
                "raw_params": {},
            })

            # New visitor: scroll event
            raw.insert_one({
                "event_type": "scroll",
                "occurred_at": self.two_weeks_ago + timedelta(seconds=30),
                "site_id": "scandinavian",
                "session_id": "sess-new-001",
                "visitor_id": self.new_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/booking",
                "raw_params": {"scroll_depth": "75"},
            })

            # New visitor: booking_confirmed
            raw.insert_one({
                "event_type": "booking_confirmed",
                "occurred_at": self.two_weeks_ago + timedelta(minutes=5),
                "site_id": "scandinavian",
                "session_id": "sess-new-001",
                "visitor_id": self.new_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/booking/confirm",
                "raw_params": {},
            })

            # New visitor: purchase
            raw.insert_one({
                "event_type": "purchase",
                "occurred_at": self.two_weeks_ago + timedelta(minutes=10),
                "site_id": "scandinavian",
                "session_id": "sess-new-001",
                "visitor_id": self.new_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "raw_params": {"revenue": "150.00"},
            })

            # Returning visitor: booking_confirmed
            raw.insert_one({
                "event_type": "booking_confirmed",
                "occurred_at": self.one_week_ago,
                "site_id": "scandinavian",
                "session_id": "sess-ret-001",
                "visitor_id": self.return_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "raw_params": {},
            })

            # Returning visitor: purchase
            raw.insert_one({
                "event_type": "purchase",
                "occurred_at": self.one_week_ago + timedelta(minutes=5),
                "site_id": "scandinavian",
                "session_id": "sess-ret-001",
                "visitor_id": self.return_visitor_id,
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "raw_params": {"revenue": "250.00"},
            })

            # Lost session: visitor views booking page but never confirms
            raw.insert_one({
                "event_type": "page_view",
                "occurred_at": self.one_week_ago + timedelta(hours=2),
                "site_id": "scandinavian",
                "session_id": "sess-lost-001",
                "visitor_id": "visitor-lost-001",
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/book-now",
                "raw_params": {},
            })

            raw.insert_one({
                "event_type": "page_view",
                "occurred_at": self.one_week_ago + timedelta(hours=2, minutes=2),
                "site_id": "scandinavian",
                "session_id": "sess-lost-001",
                "visitor_id": "visitor-lost-001",
                "utm": {"source": "google", "medium": "cpc", "campaign": "spring-ads-2026"},
                "url": "https://booking.scandinavianclinic.com/pricing",
                "raw_params": {},
            })

            # ── Seed ratings ──
            ratings_col = get_collection("therapist_ratings")
            ratings_col.insert_one({
                "therapist_id": "t001",
                "rating": 4,
                "created_at": self.one_week_ago,
            })
            ratings_col.insert_one({
                "therapist_id": "t001",
                "patient_id": "p001",
                "rating": 5,
                "created_at": self.one_week_ago,
            })
            ratings_col.insert_one({
                "therapist_id": "t002",
                "rating": 2,  # low rating
                "created_at": self.two_weeks_ago,
            })


class TestOverviewReport(TestReportsBase):
    """Section 1: Overview KPIs + weekly time series."""

    def test_overview_returns_200(self):
        resp = self.client.get("/api/reports/overview?days=90")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

    def test_overview_schema_version_and_meta(self):
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        self.assertEqual(data["report_schema_version"], 1)
        self.assertEqual(data["timezone"], "UTC")
        self.assertEqual(data["week_boundary"], "iso_monday")
        self.assertEqual(data["spend_join_method"], "whole_months")

    def test_overview_kpi_tiles_present(self):
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        tiles = data["kpi_tiles"]
        expected_keys = [
            "total_revenue_all",
            "total_revenue_new_visitors_estimated",
            "number_of_visitors",
            "number_of_new_visitors_estimated",
            "booking_confirmation_rate",
            "revenue_per_customer",
            "marketing_cost_per_customer",
            "total_marketing_spend",
        ]
        for key in expected_keys:
            self.assertIn(key, tiles, f"Missing KPI tile: {key}")

    def test_overview_revenue_is_raw(self):
        """Revenue should NOT subtract cancellations (user tweak #2)."""
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        # We seeded 150 + 250 = 400 in purchases
        self.assertEqual(data["kpi_tiles"]["total_revenue_all"], 400.00)

    def test_overview_new_visitors_labelled_estimated(self):
        """New visitor counts should use 'estimated' label (user tweak #1)."""
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        tiles = data["kpi_tiles"]
        # Key names must contain 'estimated'
        self.assertIn("number_of_new_visitors_estimated", tiles)
        self.assertIn("total_revenue_new_visitors_estimated", tiles)
        # estimated_from_visitor_id flag
        self.assertTrue(tiles["estimated_from_visitor_id"])

    def test_overview_new_visitor_revenue(self):
        """Only new visitor's revenue should be in new_visitors_estimated."""
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        # Only new_visitor_id (150.00) is new; return_visitor_id existed before
        self.assertEqual(data["kpi_tiles"]["total_revenue_new_visitors_estimated"], 150.00)

    def test_overview_weekly_series_structure(self):
        resp = self.client.get("/api/reports/overview?days=90&rollup=week")
        data = resp.get_json()
        self.assertIn("weekly_series", data)
        if data["weekly_series"]:
            entry = data["weekly_series"][0]
            self.assertIn("week_start_date", entry)
            self.assertIn("revenue_total", entry)
            self.assertIn("revenue_new_visitors_estimated", entry)
            self.assertIn("marketing_spend_total", entry)

    def test_overview_spend_from_campaigns(self):
        resp = self.client.get("/api/reports/overview?days=90")
        data = resp.get_json()
        self.assertEqual(data["kpi_tiles"]["total_marketing_spend"], 1500.00)


class TestFunnelReport(TestReportsBase):
    """Section 2: Per-campaign funnel comparison."""

    def test_funnels_returns_200(self):
        resp = self.client.get("/api/reports/funnels?days=90")
        self.assertEqual(resp.status_code, 200)

    def test_funnels_active_only_filter(self):
        """Only active campaigns should appear when scope=active_only."""
        resp = self.client.get("/api/reports/funnels?days=90&scope=active_only")
        data = resp.get_json()
        # Check schema meta
        self.assertEqual(data["report_schema_version"], 1)
        campaign_ids = [f["identifiers"]["campaign_id"] for f in data["funnels"]]
        self.assertIn(self.campaign_id, campaign_ids)
        self.assertNotIn("camp-inactive-001", campaign_ids)

    def test_funnel_booking_confirmed_count(self):
        """Funnel should count booking_confirmed events correctly."""
        resp = self.client.get("/api/reports/funnels?days=90")
        data = resp.get_json()
        test_funnel = next(
            f for f in data["funnels"]
            if f["identifiers"]["campaign_id"] == self.campaign_id
        )
        self.assertEqual(test_funnel["onsite_funnel"]["booking_confirmed"], 2)

    def test_funnel_economics(self):
        """Spend and revenue should be correctly joined."""
        resp = self.client.get("/api/reports/funnels?days=90")
        data = resp.get_json()
        test_funnel = next(
            f for f in data["funnels"]
            if f["identifiers"]["campaign_id"] == self.campaign_id
        )
        self.assertEqual(test_funnel["economics"]["spend_period"], 1500.00)
        self.assertEqual(test_funnel["economics"]["revenue_period"], 400.00)
        self.assertEqual(test_funnel["economics"]["spend_join_method"], "whole_months")

    def test_funnel_sessions_total(self):
        """Funnel should include both landing_sessions and sessions_total."""
        resp = self.client.get("/api/reports/funnels?days=90")
        data = resp.get_json()
        test_funnel = next(
            f for f in data["funnels"]
            if f["identifiers"]["campaign_id"] == self.campaign_id
        )
        self.assertIn("landing_sessions", test_funnel["top_of_funnel"])
        self.assertIn("sessions_total", test_funnel["top_of_funnel"])

    def test_funnel_stubs_present(self):
        """Uninstrumented fields should have schema stubs."""
        resp = self.client.get("/api/reports/funnels?days=90")
        data = resp.get_json()
        test_funnel = next(
            f for f in data["funnels"]
            if f["identifiers"]["campaign_id"] == self.campaign_id
        )
        self.assertEqual(test_funnel["top_of_funnel"]["impressions"]["source"], "unavailable")
        self.assertEqual(test_funnel["onsite_funnel"]["attended_first_visit"], 0)

    def test_funnel_all_scope(self):
        """scope=all should include ended campaigns too."""
        resp = self.client.get("/api/reports/funnels?days=90&scope=all")
        data = resp.get_json()
        campaign_ids = [f["identifiers"]["campaign_id"] for f in data["funnels"]]
        self.assertIn("camp-inactive-001", campaign_ids)


class TestValueReport(TestReportsBase):
    """Section 3: Long-term/value analysis."""

    def test_value_returns_200(self):
        resp = self.client.get("/api/reports/value?days=90")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["report_schema_version"], 1)

    def test_value_ratings_trends(self):
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        self.assertIn("ratings_trends", data)
        # Should have weekly entries
        if data["ratings_trends"]:
            entry = data["ratings_trends"][0]
            self.assertIn("week_start_date", entry)
            self.assertIn("therapist_rating_avg", entry)
            self.assertIn("low_rating_count", entry)

    def test_value_low_rating_detected(self):
        """Rating of 2 should count as low (<3)."""
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        total_low = sum(wk["low_rating_count"] for wk in data["ratings_trends"])
        self.assertGreaterEqual(total_low, 1)

    def test_value_new_vs_repeat_revenue(self):
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        self.assertIn("new_vs_repeat_revenue", data)
        nvr = data["new_vs_repeat_revenue"]
        self.assertTrue(nvr["estimated_from_visitor_id"])
        # Sum should match total
        new_total = sum(w["revenue_new_visitor_estimated"] for w in nvr["series"])
        repeat_total = sum(w["revenue_repeat_visitor"] for w in nvr["series"])
        self.assertAlmostEqual(new_total + repeat_total, 400.00, places=2)

    def test_value_ltv_phase_gated(self):
        """LTV should return not_available with prerequisites."""
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        self.assertEqual(data["ltv_by_rating"]["status"], "not_available")
        self.assertIn("customer_key_hash", data["ltv_by_rating"]["prerequisites"])

    def test_value_loss_analysis_has_trigger_event(self):
        """Loss analysis must include loss_trigger_event field (user tweak #3)."""
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        loss = data["loss_after_booking_page"]
        self.assertIn("loss_trigger_event", loss)
        self.assertEqual(loss["loss_trigger_event"], "page_view")

    def test_value_loss_session_detected(self):
        """Lost session (viewed booking page, no confirmation) should be counted."""
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        self.assertGreaterEqual(data["loss_after_booking_page"]["sessions_lost"], 1)

    def test_value_touchpoints(self):
        resp = self.client.get("/api/reports/value?days=90")
        data = resp.get_json()
        self.assertIn("touchpoints_before_booking", data)
        tp = data["touchpoints_before_booking"]
        self.assertIn("avg_touchpoints_before_booking", tp)
        self.assertIn("touchpoint_distribution", tp)


class TestCampaignPacket(TestReportsBase):
    """LLM report packet for a specific campaign."""

    def test_packet_returns_200(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["packet"]["report_schema_version"], 1)
        self.assertEqual(data["packet"]["timezone"], "UTC")

    def test_packet_not_found(self):
        resp = self.client.get("/api/reports/campaign/nonexistent?days=90")
        self.assertEqual(resp.status_code, 404)

    def test_packet_includes_plan_snapshot(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        self.assertIn("plan_snapshot", packet)
        self.assertEqual(packet["plan_snapshot"]["rationale"], "Drive bookings")

    def test_packet_no_pii_in_paths(self):
        """Example paths must not contain PII fields."""
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        for path in packet.get("example_paths", []):
            for step in path.get("steps", []):
                self.assertNotIn("customer_name", step)
                self.assertNotIn("customer_email", step)
                self.assertNotIn("ip_address", step)

    def test_packet_funnel_counts(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        self.assertEqual(packet["booking_funnel"]["confirmed"], 2)
        self.assertEqual(packet["economics"]["total_revenue"], 400.00)
        self.assertEqual(packet["economics"]["total_cost"], 1500.00)
        self.assertEqual(packet["economics"]["spend_join_method"], "whole_months")

    def test_packet_sessions_total(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        self.assertIn("sessions_total", packet["top_of_funnel"])
        self.assertIn("landing_sessions", packet["top_of_funnel"])

    def test_packet_quality_metrics(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        self.assertIn("quality", packet)
        self.assertIn("cancellation_rate", packet["quality"])

    def test_packet_weekly_series(self):
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        packet = data["packet"]
        self.assertIn("weekly_series", packet)
        if packet["weekly_series"]:
            entry = packet["weekly_series"][0]
            self.assertIn("bookings", entry)
            self.assertIn("revenue", entry)

    def test_packet_loss_trigger_event(self):
        """Campaign packet must also include loss_trigger_event (user tweak #3)."""
        resp = self.client.get(f"/api/reports/campaign/{self.campaign_id}?days=90")
        data = resp.get_json()
        loss = data["packet"]["loss_after_booking_page"]
        self.assertIn("loss_trigger_event", loss)


if __name__ == "__main__":
    unittest.main()
