"""
Targeted investigation of domain/host handling issues.
"""
import sys
from pathlib import Path
from pprint import pformat

sys.path.insert(0, str(Path(__file__).parent / "src"))
from src.database import get_collection

OUTPUT_FILE = Path(__file__).parent / "domain_investigation.txt"

def investigate():
    lines = []
    def p(text=""):
        lines.append(str(text))

    collection = get_collection()

    # 1. Check for stage.scandinavianclinic.com
    p("=" * 70)
    p("1. SEARCH FOR stage.scandinavianclinic.com")
    p("=" * 70)
    
    # Check host field
    stage_host = collection.count_documents({"host": {"$regex": "stage", "$options": "i"}})
    p(f"  Events with host containing 'stage': {stage_host}")
    
    # Check domain field
    stage_domain = collection.count_documents({"domain": {"$regex": "stage", "$options": "i"}})
    p(f"  Events with domain containing 'stage': {stage_domain}")
    
    # Check url in raw_params
    stage_url = collection.count_documents({"raw_params.url": {"$regex": "stage", "$options": "i"}})
    p(f"  Events with raw_params.url containing 'stage': {stage_url}")
    
    # Check full_url
    stage_full = collection.count_documents({"full_url": {"$regex": "stage", "$options": "i"}})
    p(f"  Events with full_url containing 'stage': {stage_full}")
    
    # Check site_id for scandinavian
    stage_site = collection.count_documents({"raw_params.site_id": {"$regex": "scand", "$options": "i"}})
    p(f"  Events with raw_params.site_id containing 'scand': {stage_site}")
    
    if stage_host > 0:
        sample = collection.find_one({"host": {"$regex": "stage", "$options": "i"}})
        p(f"\n  Sample event from stage host:")
        p(f"    host: {sample.get('host')}")
        p(f"    domain: {sample.get('domain')}")
        p(f"    event_type: {sample.get('event_type')}")
        p(f"    site_id: {sample.get('site_id')}")

    # 2. www.dnstrainer.com vs dnstrainer.com breakdown
    p(f"\n{'='*70}")
    p("2. www.dnstrainer.com vs dnstrainer.com BREAKDOWN")
    p("=" * 70)
    
    for host_val in ["www.dnstrainer.com", "dnstrainer.com", "www.booking.dnstrainer.com", "booking.dnstrainer.com"]:
        count = collection.count_documents({"host": host_val})
        p(f"\n  Host: {host_val} ({count} events)")
        if count > 0:
            # Show event types for this host
            pipeline = [
                {"$match": {"host": host_val}},
                {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            for r in collection.aggregate(pipeline):
                p(f"    event_type={r['_id']}: {r['count']}")
            # Show a sample with domain extracted
            sample = collection.find_one({"host": host_val})
            p(f"    domain field: {sample.get('domain')}")
            p(f"    site_id: {sample.get('site_id')}")

    # 3. Investigate why digitaltrackingsite.onrender.com appears
    p(f"\n{'='*70}")
    p("3. digitaltrackingsite.onrender.com ANALYSIS")
    p("=" * 70)
    
    render_count = collection.count_documents({"host": "digitaltrackingsite.onrender.com"})
    p(f"  Total events with host=digitaltrackingsite.onrender.com: {render_count}")
    
    # Break down by event type
    pipeline = [
        {"$match": {"host": "digitaltrackingsite.onrender.com"}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    p(f"\n  By event_type:")
    for r in collection.aggregate(pipeline):
        p(f"    {r['_id']}: {r['count']}")
    
    # Break down by site_id
    pipeline = [
        {"$match": {"host": "digitaltrackingsite.onrender.com"}},
        {"$group": {"_id": "$site_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    p(f"\n  By site_id:")
    for r in collection.aggregate(pipeline):
        p(f"    {r['_id'] or '(none)'}: {r['count']}")

    # Check if these events have a url in raw_params (which should override host)
    pipeline = [
        {"$match": {"host": "digitaltrackingsite.onrender.com"}},
        {"$group": {"_id": {"$ifNull": ["$raw_params.url", "(no url param)"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    p(f"\n  By raw_params.url (first 10):")
    for r in collection.aggregate(pipeline):
        url_val = r['_id']
        if len(str(url_val)) > 80:
            url_val = str(url_val)[:80] + "..."
        p(f"    {url_val}: {r['count']}")

    # Show a sample booking_confirmed event from render host
    sample_bc = collection.find_one({"host": "digitaltrackingsite.onrender.com", "event_type": "booking_confirmed"})
    if sample_bc:
        p(f"\n  Sample booking_confirmed from render host:")
        p(f"    utm_source: {sample_bc.get('utm_source')}")
        p(f"    site_id: {sample_bc.get('site_id')}")
        p(f"    raw_params.url: {sample_bc.get('raw_params', {}).get('url', '(none)')}")
        p(f"    full_url: {sample_bc.get('full_url', '(none)')}")

    # 4. Check how events NOT on render host arrive (i.e. frontend events)
    p(f"\n{'='*70}")
    p("4. NON-RENDER HOST EVENTS (frontend-sourced)")
    p("=" * 70)
    
    pipeline = [
        {"$match": {"host": {"$ne": "digitaltrackingsite.onrender.com"}}},
        {"$group": {"_id": {"host": "$host", "event_type": "$event_type"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    for r in collection.aggregate(pipeline):
        p(f"  host={r['_id'].get('host')}, type={r['_id'].get('event_type')}: {r['count']}")

    # Write output
    output = "\n".join(lines)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"Investigation written to {OUTPUT_FILE}")

if __name__ == "__main__":
    investigate()
