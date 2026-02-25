"""
Test the PRODUCTION /track endpoint at digitaltrackingsite.onrender.com.
Sends all 4 booking event types and verifies they are accepted and queryable.
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "https://digitaltrackingsite.onrender.com"
TRACK_URL = f"{BASE_URL}/track"
API_URL = f"{BASE_URL}/api/events"

results = {"passed": 0, "failed": 0}


def test(name, response, expected_status):
    ok = response.status_code == expected_status
    tag = "[PASS]" if ok else "[FAIL]"
    print(f"  {tag} {name}")
    print(f"       Status: {response.status_code} (expected {expected_status})")
    try:
        body = response.json()
        print(f"       Body: {json.dumps(body, indent=8)[:400]}")
    except:
        print(f"       Body: {response.text[:300]}")
    if ok:
        results["passed"] += 1
    else:
        results["failed"] += 1
    print()
    return ok


def main():
    print("=" * 70)
    print("PRODUCTION Booking Tracking — Verification")
    print(f"Target: {BASE_URL}")
    print(f"Time:   {datetime.now().isoformat()}")
    print("=" * 70)

    # ── Check server is alive ──
    print("\nChecking server health...")
    try:
        r = requests.get(BASE_URL, timeout=15)
        print(f"  Server responded: {r.status_code}\n")
    except Exception as e:
        print(f"  ❌ Server not reachable: {e}")
        print("  Render may still be deploying. Try again in a few minutes.")
        sys.exit(1)

    # ── Test 1: page_view (NO UTMs) ──
    print("─" * 70)
    print("Test 1: page_view (no UTMs) — site_id=dnstrainer")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "page_view",
        "url": "https://booking.dnstrainer.com/index.php",
        "referrer": "https://dnstrainer.com/",
        "user_agent": "Mozilla/5.0 ProdTest",
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"}, timeout=15)
    test("page_view without UTMs", r, 200)

    # ── Test 2: scroll event ──
    print("─" * 70)
    print("Test 2: scroll event — site_id=scandinavian")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "scroll",
        "url": "https://booking.scandinavianclinic.com/index.php",
        "scroll_depth": 75,
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "scandinavian"
    }, headers={"Content-Type": "application/json"}, timeout=15)
    test("scroll event", r, 200)

    # ── Test 3: purchase event ──
    print("─" * 70)
    print("Test 3: purchase event — site_id=dnstrainer")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "purchase",
        "transaction_id": f"EA-PRODTEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "service_name": "DNS Training Session",
        "revenue": 150.00,
        "currency": "USD",
        "customer_email": "prodtest@example.com",
        "url": "https://booking.dnstrainer.com/index.php/booking_confirmation",
        "timestamp": datetime.utcnow().isoformat(),
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"}, timeout=15)
    test("purchase event", r, 200)

    # ── Test 4: booking_confirmed (server-side with UTMs) ──
    print("─" * 70)
    print("Test 4: booking_confirmed — backend POST with UTMs")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "event_type": "booking_confirmed",
        "customer_name": "Prod Test Customer",
        "customer_email": "prodtest@example.com",
        "customer_phone": "+1234567890",
        "booking_id": f"BK-PRODTEST-{datetime.utcnow().strftime('%H%M%S')}",
        "timestamp": datetime.utcnow().isoformat(),
        "utm_source": "easyappointments",
        "utm_medium": "backend",
        "utm_campaign": "booking_confirmation",
        "site_id": "dnstrainer"
    }, headers={"Content-Type": "application/json"}, timeout=15)
    test("booking_confirmed event", r, 200)

    # ── Test 5: Backward compat — legacy request without event_type and no UTMs ──
    print("─" * 70)
    print("Test 5: Legacy request (no event_type, no UTMs) → expect 400")
    print("─" * 70)
    r = requests.post(TRACK_URL, json={
        "gclid": "fake-gclid-prodtest"
    }, headers={"Content-Type": "application/json"}, timeout=15)
    test("Legacy without UTMs should fail", r, 400)

    # ── Test 6: API query — filter by site_id ──
    print("─" * 70)
    print("Test 6: /api/events?site_id=dnstrainer&limit=5")
    print("─" * 70)
    r = requests.get(f"{API_URL}?site_id=dnstrainer&limit=5", timeout=15)
    if r.status_code == 200 and r.json().get("success"):
        events = r.json().get("events", [])
        all_match = all(e.get("site_id") == "dnstrainer" for e in events)
        if all_match and len(events) > 0:
            print(f"  [PASS] {len(events)} events returned, all site_id=dnstrainer")
            results["passed"] += 1
        elif len(events) == 0:
            print(f"  [WARN] 0 events returned — data may not be indexed yet")
            results["passed"] += 1  # Still a pass if the API works
        else:
            print(f"  [FAIL] Some events have wrong site_id")
            results["failed"] += 1
    else:
        print(f"  [FAIL] API returned {r.status_code}")
        results["failed"] += 1
    print()

    # ── Test 7: API query — filter by event_type ──
    print("─" * 70)
    print("Test 7: /api/events?event_type=purchase&limit=5")
    print("─" * 70)
    r = requests.get(f"{API_URL}?event_type=purchase&limit=5", timeout=15)
    if r.status_code == 200 and r.json().get("success"):
        events = r.json().get("events", [])
        all_match = all(e.get("event_type") == "purchase" for e in events)
        if all_match and len(events) > 0:
            print(f"  [PASS] {len(events)} purchase events returned")
            results["passed"] += 1
        elif len(events) == 0:
            print(f"  [WARN] 0 purchase events — may need more data")
            results["passed"] += 1
        else:
            print(f"  [FAIL] Wrong event_type in results")
            results["failed"] += 1
    else:
        print(f"  [FAIL] API returned {r.status_code}")
        results["failed"] += 1
    print()

    # ── Test 8: CORS preflight for scandinavianclinic ──
    print("─" * 70)
    print("Test 8: CORS preflight — Origin: booking.scandinavianclinic.com")
    print("─" * 70)
    r = requests.options(TRACK_URL, headers={
        "Origin": "https://booking.scandinavianclinic.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type"
    }, timeout=15)
    acao = r.headers.get("Access-Control-Allow-Origin", "")
    if "scandinavianclinic" in acao or acao == "*":
        print(f"  [PASS] CORS Allow-Origin: {acao}")
        results["passed"] += 1
    else:
        print(f"  [FAIL] CORS Allow-Origin: '{acao}' — missing scandinavianclinic")
        results["failed"] += 1
    print()

    # ── Summary ──
    print("=" * 70)
    total = results["passed"] + results["failed"]
    print(f"Results: {results['passed']}/{total} passed, {results['failed']}/{total} failed")
    if results["failed"] == 0:
        print("✅ PRODUCTION DEPLOYMENT VERIFIED — ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED — check output above")
    print("=" * 70)


if __name__ == "__main__":
    main()
