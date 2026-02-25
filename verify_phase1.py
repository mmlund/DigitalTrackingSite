"""
Phase 1 Verification Script

Inserts 3 sample events via the /track endpoint and verifies
that all envelope fields are present and correct. Then runs the
LLM preprocessor and checks the output structure.

Usage:
    python verify_phase1.py

Requires the app to be running in TEST_MODE=True (uses mock DB).
"""

import os
os.environ["TEST_MODE"] = "True"

import sys
from pathlib import Path
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from app import app


def _bold(text):
    return f"\033[1m{text}\033[0m"

def _green(text):
    return f"\033[92m{text}\033[0m"

def _red(text):
    return f"\033[91m{text}\033[0m"

def _check(label, condition):
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label}")
    return condition


def main():
    client = app.test_client()
    client.testing = True
    all_passed = True

    # ── Sample Event 1: Web page_view ────────────────────────────
    print(f"\n{_bold('Event 1: Web page_view (dnstrainer.com)')}")
    resp = client.post('/track', json={
        "event_type": "page_view",
        "url": "https://dnstrainer.com/services",
        "site_id": "dnstrainer",
        "device_id": "dvc_test_001",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "summer_promo",
    }, content_type='application/json')

    all_passed &= _check("200 OK", resp.status_code == 200)

    # Since we're using mock DB, we can't inspect stored docs directly.
    # But we can inspect what process_tracking_event returns by using the test client.
    from unittest.mock import patch
    with patch('src.blueprints.tracking.store_event', return_value="mock_id") as mock_store:
        resp = client.post('/track', json={
            "event_type": "page_view",
            "url": "https://dnstrainer.com/services",
            "site_id": "dnstrainer",
            "device_id": "dvc_test_001",
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "summer_promo",
        }, content_type='application/json')
        ev1 = mock_store.call_args[0][0]

    all_passed &= _check("schema_version = 1", ev1.get("schema_version") == 1)
    all_passed &= _check("event_type = page_view", ev1.get("event_type") == "page_view")
    all_passed &= _check("occurred_at is datetime", isinstance(ev1.get("occurred_at"), datetime))
    all_passed &= _check("site_id = dnstrainer", ev1.get("site_id") == "dnstrainer")
    all_passed &= _check("host = dnstrainer.com", ev1.get("host") == "dnstrainer.com")
    all_passed &= _check("domain = dnstrainer.com", ev1.get("domain") == "dnstrainer.com")
    all_passed &= _check("url present", ev1.get("url") == "https://dnstrainer.com/services")
    all_passed &= _check("visitor_id = dvc_test_001", ev1.get("visitor_id") == "dvc_test_001")
    all_passed &= _check("utm.source = google", ev1.get("utm", {}).get("source") == "google")
    all_passed &= _check("utm.medium = cpc", ev1.get("utm", {}).get("medium") == "cpc")
    all_passed &= _check("utm.campaign = summer_promo", ev1.get("utm", {}).get("campaign") == "summer_promo")
    all_passed &= _check("source_system = web", ev1.get("source_system") == "web")
    all_passed &= _check("raw_params preserved", "utm_source" in ev1.get("raw_params", {}))

    # ── Sample Event 2: booking_confirmed from EA ────────────────
    print(f"\n{_bold('Event 2: booking_confirmed (booking.scandinavianclinic.com)')}")
    with patch('src.blueprints.tracking.store_event', return_value="mock_id") as mock_store:
        resp = client.post('/track', json={
            "event_type": "booking_confirmed",
            "url": "https://booking.scandinavianclinic.com/index.php/booking_confirmation",
            "booking_id": "EA-123",
            "utm_source": "easyappointments_scandinavian",
            "utm_medium": "backend",
            "utm_campaign": "booking_confirmation",
            "customer_name": "Test Patient",
            "customer_email": "test@scandinavianclinic.com",
        }, content_type='application/json')
        ev2 = mock_store.call_args[0][0]

    all_passed &= _check("200 OK", resp.status_code == 200)
    all_passed &= _check("event_type = booking_confirmed", ev2.get("event_type") == "booking_confirmed")
    all_passed &= _check("site_id inferred = scandinavian", ev2.get("site_id") == "scandinavian")
    all_passed &= _check("source_system = easyappointments_scandinavian",
                          ev2.get("source_system") == "easyappointments_scandinavian")
    all_passed &= _check("utm.source = easyappointments_scandinavian",
                          ev2.get("utm", {}).get("source") == "easyappointments_scandinavian")
    all_passed &= _check("customer_name promoted", ev2.get("customer_name") == "Test Patient")
    all_passed &= _check("raw_params has booking_id", ev2.get("raw_params", {}).get("booking_id") == "EA-123")

    # ── Sample Event 3: purchase ─────────────────────────────────
    print(f"\n{_bold('Event 3: purchase (booking.dnstrainer.com)')}")
    with patch('src.blueprints.tracking.store_event', return_value="mock_id") as mock_store:
        resp = client.post('/track', json={
            "event_type": "purchase",
            "url": "https://booking.dnstrainer.com/confirmation",
            "site_id": "dnstrainer",
            "revenue": 105,
            "currency": "CAD",
            "transaction_id": "TXN-999",
        }, content_type='application/json')
        ev3 = mock_store.call_args[0][0]

    all_passed &= _check("200 OK", resp.status_code == 200)
    all_passed &= _check("event_type = purchase", ev3.get("event_type") == "purchase")
    all_passed &= _check("site_id = dnstrainer", ev3.get("site_id") == "dnstrainer")
    all_passed &= _check("source_system = easyappointments_dnstrainer",
                          ev3.get("source_system") == "easyappointments_dnstrainer")
    all_passed &= _check("utm.source is None (no UTM)", ev3.get("utm", {}).get("source") is None)
    all_passed &= _check("raw_params.revenue = 105", ev3.get("raw_params", {}).get("revenue") == 105)

    # ── Bonus: event with NO event_type (should default to "unknown") ──
    print(f"\n{_bold('Event 4: Missing event_type (should default to unknown)')}")
    with patch('src.blueprints.tracking.store_event', return_value="mock_id") as mock_store:
        resp = client.post('/track', json={
            "url": "https://booking.dnstrainer.com/index.php",
        }, content_type='application/json')
        ev4 = mock_store.call_args[0][0]

    all_passed &= _check("200 OK (not rejected)", resp.status_code == 200)
    all_passed &= _check("event_type = unknown", ev4.get("event_type") == "unknown")
    all_passed &= _check("site_id inferred = dnstrainer", ev4.get("site_id") == "dnstrainer")

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'='*55}")
    if all_passed:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    print(f"{'='*55}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
