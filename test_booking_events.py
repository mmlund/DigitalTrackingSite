"""
Test script for booking tracking events.
Tests all 4 event types: page_view, scroll, purchase, booking_confirmed.
Also validates site_id filtering via /api/events.
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:5000"
TRACK_URL = f"{BASE_URL}/track"
API_URL = f"{BASE_URL}/api/events"

results = {"passed": 0, "failed": 0}


def test(name, response, expected_status):
    """Helper to print test result."""
    ok = response.status_code == expected_status
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag} {name}")
    print(f"       Status: {response.status_code} (expected {expected_status})")
    try:
        body = response.json()
        print(f"       Body: {json.dumps(body, indent=8)[:300]}")
    except:
        print(f"       Body: {response.text[:200]}")
    if ok:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    return ok


def main():
    print("=" * 70)
    print("Booking Tracking Events — Test Suite")
    print("=" * 70)

    # Check server
    try:
        requests.get(BASE_URL, timeout=2)
        print("✅ Server is running\n")
    except Exception:
        print("❌ Server not reachable at", BASE_URL)
        print("   Start with: python app.py")
        sys.exit(1)

    # ── Test 1: page_view (no UTMs — this is the 400 bug scenario) ──
    print("─" * 70)
    print("Test 1: page_view event (NO UTMs) — site_id=dnstrainer")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "page_view",
        "url": "https://booking.dnstrainer.com/index.php",
        "referrer": "https://dnstrainer.com/",
        "user_agent": "Mozilla/5.0 Test",
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"})
    test("page_view without UTMs should succeed", r, 200)

    # ── Test 2: scroll event ──
    print("─" * 70)
    print("Test 2: scroll event — site_id=scandinavian")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "scroll",
        "url": "https://booking.scandinavianclinic.com/index.php",
        "scroll_depth": 50,
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "scandinavian"
    }, headers={"Content-Type": "application/json"})
    test("scroll event should succeed", r, 200)

    # ── Test 3: purchase event ──
    print("─" * 70)
    print("Test 3: purchase event — site_id=dnstrainer")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "purchase",
        "transaction_id": "EA-20260209-001",
        "service_name": "DNS Training Session",
        "revenue": 150.00,
        "currency": "USD",
        "customer_email": "test@example.com",
        "url": "https://booking.dnstrainer.com/index.php/booking_confirmation",
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"})
    test("purchase event should succeed", r, 200)

    # ── Test 4: booking_confirmed (server-side with UTMs) ──
    print("─" * 70)
    print("Test 4: booking_confirmed event (with UTMs) — backend POST")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "booking_confirmed",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "customer_phone": "+1234567890",
        "booking_id": "BK-12345",
        "timestamp": datetime.utcnow().isoformat(),
        "utm_source": "easyappointments",
        "utm_medium": "backend",
        "utm_campaign": "booking_confirmation",
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"})
    test("booking_confirmed event should succeed", r, 200)

    # ── Test 5: Legacy ad-click WITHOUT UTMs — should still fail (backward compat) ──
    print("─" * 70)
    print("Test 5: Legacy request without event_type and no UTMs → should 400")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "gclid": "fake-gclid-123"
    }, headers={"Content-Type": "application/json"})
    test("Legacy request without UTMs should fail", r, 400)

    # ── Test 6: page_view with UTMs for Scandinavian ──
    print("─" * 70)
    print("Test 6: page_view with UTMs — site_id=scandinavian")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "page_view",
        "url": "https://booking.scandinavianclinic.com/",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "scandinavian_launch",
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "scandinavian"
    }, headers={"Content-Type": "application/json"})
    test("page_view with UTMs for scandinavian should succeed", r, 200)

    # ── Test 7: API query — filter by site_id ──
    print("─" * 70)
    print("Test 7: /api/events?site_id=dnstrainer")
    print("─" * 70)
    r = requests.get(f"{API_URL}?site_id=dnstrainer")
    ok = r.status_code == 200 and r.json().get("success")
    if ok:
        events = r.json().get("events", [])
        # Check all returned events have site_id=dnstrainer
        all_match = all(e.get("site_id") == "dnstrainer" for e in events)
        if all_match:
            print(f"  [PASS] Returned {len(events)} events, all site_id=dnstrainer")
            results["passed"] += 1
        else:
            print(f"  [FAIL] Some events have wrong site_id!")
            results["failed"] += 1
    else:
        print(f"  [FAIL] API returned status={r.status_code}")
        results["failed"] += 1
    print()

    # ── Test 8: API query — filter by event_type ──
    print("─" * 70)
    print("Test 8: /api/events?event_type=purchase")
    print("─" * 70)
    r = requests.get(f"{API_URL}?event_type=purchase")
    ok = r.status_code == 200 and r.json().get("success")
    if ok:
        events = r.json().get("events", [])
        all_match = all(e.get("event_type") == "purchase" for e in events)
        if all_match:
            print(f"  [PASS] Returned {len(events)} purchase events")
            results["passed"] += 1
        else:
            print(f"  [FAIL] Some events have wrong event_type!")
            results["failed"] += 1
    else:
        print(f"  [FAIL] API returned status={r.status_code}")
        results["failed"] += 1
    print()

    # ── Summary ──
    print("=" * 70)
    total = results["passed"] + results["failed"]
    print(f"Results: {results['passed']}/{total} passed, {results['failed']}/{total} failed")
    if results["failed"] == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)


if __name__ == "__main__":
    main()
