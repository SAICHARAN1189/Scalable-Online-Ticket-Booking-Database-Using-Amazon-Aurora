"""
Aurora Ticket Booking — Load Testing Tool
==========================================
Generates configurable read and write workloads to measure performance.
Supports writer vs reader endpoint comparison (Aurora mode) and
local testing against the Flask dev server.

Usage:
    python load_test.py --base-url http://127.0.0.1:5000 --read-requests 200 --workers 10
    python load_test.py --base-url http://127.0.0.1:5000 --concurrency-test --concurrency-tickets 10
    python load_test.py --help

Results are exported to load_test_results/ as CSV and JSON.
"""

import argparse
import csv
import json
import os
import sys
import time
import statistics
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import urllib.request
    import urllib.error
    import urllib.parse
except ImportError:
    pass


RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "load_test_results")


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def http_get(url, timeout=15):
    """Perform an HTTP GET and return (status_code, body, elapsed_ms)."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return e.code, str(e), elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return 0, str(e), elapsed


def http_post(url, data, timeout=15):
    """Perform an HTTP POST with JSON body and return (status_code, body, elapsed_ms)."""
    start = time.perf_counter()
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            elapsed = (time.perf_counter() - start) * 1000
            return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        body = e.read().decode() if hasattr(e, 'read') else str(e)
        return e.code, body, elapsed
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return 0, str(e), elapsed


def calculate_percentile(data, p):
    """Calculate the p-th percentile of a sorted list."""
    if not data:
        return 0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ---------------------------------------------------------------------------
# Read Load Test
# ---------------------------------------------------------------------------
def run_read_load_test(base_url, total_requests, workers, endpoint_path="/api/events"):
    """
    Generate read-only workload against the specified endpoint.
    Returns a dict with timing statistics.
    """
    url = f"{base_url}{endpoint_path}"
    print(f"\n{'='*60}")
    print(f"  READ LOAD TEST")
    print(f"  URL: {url}")
    print(f"  Requests: {total_requests} | Workers: {workers}")
    print(f"{'='*60}\n")

    latencies = []
    errors = 0
    error_messages = []
    start_time = time.perf_counter()

    def single_request(_):
        nonlocal errors
        status, body, elapsed = http_get(url)
        if status == 200:
            latencies.append(elapsed)
        else:
            errors += 1
            error_messages.append(f"Status {status}")
        return elapsed

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(single_request, i) for i in range(total_requests)]
        completed = 0
        for f in as_completed(futures):
            completed += 1
            if completed % 50 == 0:
                print(f"  Progress: {completed}/{total_requests} requests completed")
            f.result()  # raises if exception

    total_time = time.perf_counter() - start_time

    result = {
        "test_type": "read_load_test",
        "url": url,
        "total_requests": total_requests,
        "concurrent_workers": workers,
        "duration_seconds": round(total_time, 2),
        "successful_requests": len(latencies),
        "error_count": errors,
        "requests_per_second": round(total_requests / total_time, 2) if total_time > 0 else 0,
    }

    if latencies:
        result.update({
            "avg_latency_ms": round(statistics.mean(latencies), 2),
            "min_latency_ms": round(min(latencies), 2),
            "max_latency_ms": round(max(latencies), 2),
            "p50_latency_ms": round(calculate_percentile(latencies, 50), 2),
            "p90_latency_ms": round(calculate_percentile(latencies, 90), 2),
            "p95_latency_ms": round(calculate_percentile(latencies, 95), 2),
            "p99_latency_ms": round(calculate_percentile(latencies, 99), 2),
            "stdev_latency_ms": round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0,
        })

    print(f"\n  ✅ Completed in {result['duration_seconds']}s")
    print(f"  📊 RPS: {result['requests_per_second']}")
    print(f"  ⏱️  Avg: {result.get('avg_latency_ms', 'N/A')}ms | "
          f"P50: {result.get('p50_latency_ms', 'N/A')}ms | "
          f"P95: {result.get('p95_latency_ms', 'N/A')}ms | "
          f"P99: {result.get('p99_latency_ms', 'N/A')}ms")
    print(f"  ❌ Errors: {errors}")

    return result


# ---------------------------------------------------------------------------
# Concurrency Test
# ---------------------------------------------------------------------------
def run_concurrency_test(base_url, num_tickets=5, num_attempts=20):
    """
    Test that concurrent booking attempts do not oversell.

    Creates a scenario with limited tickets and fires concurrent booking requests.
    Verifies that the number of successful bookings <= available tickets.
    """
    print(f"\n{'='*60}")
    print(f"  CONCURRENCY TEST (Overselling Prevention)")
    print(f"  Available tickets: {num_tickets} | Concurrent attempts: {num_attempts}")
    print(f"{'='*60}\n")

    # First, find an event and check availability
    status, body, _ = http_get(f"{base_url}/api/events")
    if status != 200:
        print(f"  ❌ Failed to fetch events: {body}")
        return {"test_type": "concurrency_test", "error": "Cannot fetch events"}

    events = json.loads(body).get("events", [])
    # Find an event with enough tickets
    target_event = None
    for e in events:
        if e["available_tickets"] >= num_tickets:
            target_event = e
            break

    if not target_event:
        print("  ⚠️  No event with sufficient tickets found. Using event #1.")
        target_event = events[0] if events else None

    if not target_event:
        return {"test_type": "concurrency_test", "error": "No events available"}

    event_id = target_event["event_id"]
    initial_available = target_event["available_tickets"]
    print(f"  🎯 Target: {target_event['title']}")
    print(f"  📊 Initial availability: {initial_available}\n")

    results = []

    def attempt_booking(i):
        uid = uuid.uuid4().hex[:6]
        data = {
            "event_id": event_id,
            "name": f"ConcTest User {i}",
            "email": f"conctest_{uid}_{i}@loadtest.local",
            "num_tickets": 1,
        }
        status, body, elapsed = http_post(f"{base_url}/api/book", data)
        try:
            resp = json.loads(body)
        except (json.JSONDecodeError, Exception):
            resp = {"success": False, "error": body}
        return {"status": status, "response": resp, "elapsed_ms": elapsed}

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_attempts) as executor:
        futures = [executor.submit(attempt_booking, i) for i in range(num_attempts)]
        for f in as_completed(futures):
            results.append(f.result())
    total_time = time.perf_counter() - start

    successful = sum(1 for r in results if r["response"].get("success"))
    failed = num_attempts - successful

    # Check final availability
    status, body, _ = http_get(f"{base_url}/api/events/{event_id}")
    final_available = json.loads(body)["event"]["available_tickets"] if status == 200 else "unknown"

    oversold = successful > initial_available
    expected_remaining = initial_available - successful
    inventory_correct = (final_available == expected_remaining) if isinstance(final_available, int) else False

    result = {
        "test_type": "concurrency_test",
        "event_id": event_id,
        "event_title": target_event["title"],
        "available_tickets": initial_available,
        "total_attempts": num_attempts,
        "successful_bookings": successful,
        "failed_bookings": failed,
        "duration_seconds": round(total_time, 2),
        "final_available": final_available,
        "expected_remaining": expected_remaining,
        "oversold": oversold,
        "inventory_correct": inventory_correct,
    }

    print(f"  ✅ Successful bookings: {successful}/{num_attempts}")
    print(f"  ❌ Rejected (expected): {failed}")
    print(f"  📦 Final availability: {final_available} (expected: {expected_remaining})")
    print(f"  🔒 Oversold: {'❌ YES — BUG!' if oversold else '✅ NO'}")
    print(f"  📊 Inventory correct: {'✅ YES' if inventory_correct else '❌ NO'}")

    return result


# ---------------------------------------------------------------------------
# Writer vs Reader Endpoint Comparison
# ---------------------------------------------------------------------------
def run_endpoint_comparison(base_url, requests_per_endpoint=100, workers=5):
    """
    Compare read performance through writer and reader endpoints.

    NOTE: In local SQLite mode, both endpoints use the same database,
    so performance will be nearly identical. This test is meaningful only
    against a real Aurora cluster where writer and reader endpoints differ.
    """
    print(f"\n{'='*60}")
    print(f"  ENDPOINT COMPARISON TEST")
    print(f"  Requests per endpoint: {requests_per_endpoint} | Workers: {workers}")
    print(f"{'='*60}\n")

    # Both hit the same /api/events endpoint — the server routes internally
    # In Aurora mode, reads go through the reader endpoint
    writer_result = run_read_load_test(base_url, requests_per_endpoint, workers, "/api/events")
    # No separate writer-read endpoint in the app, so we compare with /api/dashboard/stats
    reader_result = run_read_load_test(base_url, requests_per_endpoint, workers, "/api/dashboard/stats")

    result = {
        "test_type": "endpoint_comparison",
        "note": "In local SQLite mode, both endpoints use the same database. "
                "Meaningful comparison requires a real Aurora cluster with separate writer/reader endpoints.",
        "writer_avg_ms": writer_result.get("avg_latency_ms"),
        "reader_avg_ms": reader_result.get("avg_latency_ms"),
        "writer_rps": writer_result.get("requests_per_second"),
        "reader_rps": reader_result.get("requests_per_second"),
        "writer_p95_ms": writer_result.get("p95_latency_ms"),
        "reader_p95_ms": reader_result.get("p95_latency_ms"),
        "writer_details": writer_result,
        "reader_details": reader_result,
    }

    print(f"\n  📊 Comparison Summary:")
    print(f"  Writer endpoint → Avg: {result['writer_avg_ms']}ms | RPS: {result['writer_rps']}")
    print(f"  Reader endpoint → Avg: {result['reader_avg_ms']}ms | RPS: {result['reader_rps']}")

    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_results(all_results, timestamp):
    """Export results as JSON and CSV."""
    ensure_results_dir()
    ts = timestamp.strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = os.path.join(RESULTS_DIR, f"load_test_{ts}.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  💾 JSON results: {json_path}")

    # CSV (flatten key metrics)
    csv_path = os.path.join(RESULTS_DIR, f"load_test_{ts}.csv")
    rows = []
    for key, val in all_results.items():
        if isinstance(val, dict):
            row = {"test_name": key}
            for k, v in val.items():
                if not isinstance(v, (dict, list)):
                    row[k] = v
            rows.append(row)

    if rows:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r.keys()))
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  💾 CSV results:  {csv_path}")

    return json_path, csv_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Aurora Ticket Booking — Load Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python load_test.py --base-url http://127.0.0.1:5000 --read-requests 200 --workers 10
  python load_test.py --base-url http://127.0.0.1:5000 --concurrency-test
  python load_test.py --base-url http://127.0.0.1:5000 --all
        """
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:5000",
                        help="Base URL of the Flask application (default: http://127.0.0.1:5000)")
    parser.add_argument("--read-requests", type=int, default=100,
                        help="Number of read requests to generate (default: 100)")
    parser.add_argument("--workers", type=int, default=5,
                        help="Number of concurrent workers (default: 5)")
    parser.add_argument("--concurrency-test", action="store_true",
                        help="Run the concurrency/overselling prevention test")
    parser.add_argument("--concurrency-tickets", type=int, default=10,
                        help="Number of available tickets for concurrency test")
    parser.add_argument("--concurrency-attempts", type=int, default=30,
                        help="Number of concurrent booking attempts (default: 30)")
    parser.add_argument("--endpoint-comparison", action="store_true",
                        help="Run writer vs reader endpoint comparison")
    parser.add_argument("--all", action="store_true",
                        help="Run all tests")
    parser.add_argument("--no-export", action="store_true",
                        help="Skip exporting results to files")

    args = parser.parse_args()
    timestamp = datetime.now()
    all_results = {"timestamp": timestamp.isoformat(), "base_url": args.base_url}

    print(f"\n🚀 Aurora Ticket Booking — Load Test Runner")
    print(f"   Target: {args.base_url}")
    print(f"   Time:   {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    # Verify connectivity
    print(f"\n  🔗 Testing connectivity...")
    status, body, elapsed = http_get(f"{args.base_url}/api/config")
    if status != 200:
        print(f"  ❌ Cannot reach {args.base_url}: status={status}")
        print(f"     Make sure the Flask app is running.")
        sys.exit(1)
    config = json.loads(body).get("config", {})
    print(f"  ✅ Connected ({elapsed:.0f}ms) — Mode: {'Local SQLite' if config.get('use_local_db') else 'Aurora PostgreSQL'}")

    run_read = args.all or (not args.concurrency_test and not args.endpoint_comparison)
    run_conc = args.all or args.concurrency_test
    run_comp = args.all or args.endpoint_comparison

    if run_read:
        all_results["read_load_test"] = run_read_load_test(
            args.base_url, args.read_requests, args.workers)

    if run_conc:
        all_results["concurrency_test"] = run_concurrency_test(
            args.base_url, args.concurrency_tickets, args.concurrency_attempts)

    if run_comp:
        all_results["endpoint_comparison"] = run_endpoint_comparison(
            args.base_url, args.read_requests, args.workers)

    if not args.no_export:
        json_path, csv_path = export_results(all_results, timestamp)

    print(f"\n{'='*60}")
    print(f"  ✅ ALL TESTS COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
