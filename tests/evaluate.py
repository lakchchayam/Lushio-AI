"""
Lushio AI – Evaluation Harness
Sends test_queries.json to the /ask endpoint and measures:
  1. Product Detection Accuracy (did the API find the expected products?)
  2. Stock Status Accuracy (in-stock vs out-of-stock correctness)
  3. Response Latency (per-query and average)

NOTE: Each query triggers 3-5 Groq LLM calls internally.
      A delay between queries prevents hitting the 30 req/min rate limit.
"""

import json
import time
import requests
import sys
import os

API_URL = "http://localhost:8000/ask"
TEST_FILE = "test_queries.json"
QUERY_DELAY = 10  # seconds between queries to respect Groq's ~30 req/min limit


def load_tests():
    test_file_path = os.path.join(os.path.dirname(__file__), TEST_FILE)
    with open(test_file_path, "r") as f:
        return json.load(f)


def normalize(name: str) -> str:
    """Lowercase and strip for fuzzy matching."""
    return name.lower().strip()


def check_product_match(expected_products, items_found):
    """
    Check how many expected products were returned by the API.
    Returns (matched_count, total_expected, details_list)
    """
    if len(expected_products) == 0:
        if len(items_found) == 0:
            return 1, 1, ["  ✅ Correctly fetched no products for RAG query"]
        else:
            return 0, 1, ["  ❌ Fetched products for RAG-only query"]

    found_names = [normalize(item.get("name", "")) for item in items_found]
    matched = 0
    details = []

    for exp in expected_products:
        exp_norm = normalize(exp)
        # Fuzzy: check if expected name is a substring of any found name or vice versa
        hit = any(exp_norm in fn or fn in exp_norm for fn in found_names)
        if hit:
            matched += 1
            details.append(f"  ✅ '{exp}' found")
        else:
            details.append(f"  ❌ '{exp}' NOT found")

    return matched, len(expected_products), details


def check_stock_accuracy(expected_products, expected_stock_gt_zero, items_found):
    """
    Check if the stock > 0 status matches the expected ground truth.
    Returns (correct_count, total, details_list)
    """
    if len(expected_products) == 0:
        if len(items_found) == 0:
            return 1, 1, ["  ✅ Correctly fetched no stock for RAG query"]
        else:
            return 0, 1, ["  ❌ Fetched stock for RAG-only query"]

    found_map = {}
    for item in items_found:
        found_map[normalize(item.get("name", ""))] = item

    correct = 0
    total = 0
    details = []

    for i, exp in enumerate(expected_products):
        if i >= len(expected_stock_gt_zero):
            break
        total += 1
        exp_norm = normalize(exp)

        # Find the matching item
        matched_item = None
        for fn, item_data in found_map.items():
            if exp_norm in fn or fn in exp_norm:
                matched_item = item_data
                break

        if matched_item is None:
            # Product not returned at all
            if not expected_stock_gt_zero[i]:
                correct += 1
                details.append(f"  ✅ '{exp}' correctly not found (expected no stock)")
            else:
                details.append(f"  ❌ '{exp}' missing from response (expected in stock)")
        else:
            actual_stock = matched_item.get("stock", 0)
            actual_gt_zero = actual_stock > 0
            expected_gt = expected_stock_gt_zero[i]
            if actual_gt_zero == expected_gt:
                correct += 1
                details.append(f"  ✅ '{exp}' stock={actual_stock} (correct)")
            else:
                details.append(f"  ❌ '{exp}' stock={actual_stock}, expected {'in stock' if expected_gt else 'out of stock'}")

    return correct, total, details


def run_evaluation():
    tests = load_tests()
    print(f"\n{'='*60}")
    print(f"  🧪 LUSHIO AI EVALUATION HARNESS")
    print(f"  📋 {len(tests)} test queries loaded")
    print(f"  🌐 Target: {API_URL}")
    print(f"{'='*60}\n")

    results = []

    for test in tests:
        qid = test["id"]
        query = test["query"]
        expected_products = test["expected_products"]
        expected_stock_gt_zero = test.get("expected_stock_gt_zero", [])

        print(f"─── Query #{qid}: \"{query}\"")

        try:
            start = time.time()
            resp = requests.post(API_URL, json={"query": query}, timeout=30)
            latency = round(time.time() - start, 2)

            if resp.status_code != 200:
                print(f"  ⚠️  API returned status {resp.status_code}")
                results.append({
                    "id": qid, "query": query,
                    "product_accuracy": 0, "stock_accuracy": 0,
                    "latency": latency, "error": True
                })
                continue

            data = resp.json()
            items_found = data.get("items_found", [])
            final_answer = data.get("final_answer", {})

            # 1. Product Detection
            p_matched, p_total, p_details = check_product_match(expected_products, items_found)
            p_acc = (p_matched / p_total * 100) if p_total > 0 else 0

            # 2. Stock Status
            s_correct, s_total, s_details = check_stock_accuracy(
                expected_products, expected_stock_gt_zero, items_found
            )
            s_acc = (s_correct / s_total * 100) if s_total > 0 else 0

            print(f"  ⏱️  Latency: {latency}s")
            print(f"  🎯 Product Accuracy: {p_matched}/{p_total} ({p_acc:.0f}%)")
            for d in p_details:
                print(d)
            print(f"  📦 Stock Accuracy: {s_correct}/{s_total} ({s_acc:.0f}%)")
            for d in s_details:
                print(d)

            # Show final message
            msg = final_answer.get("message", "(no message)") if isinstance(final_answer, dict) else str(final_answer)[:100]
            print(f"  💬 Answer: {msg}")

            results.append({
                "id": qid, "query": query,
                "product_accuracy": p_acc,
                "stock_accuracy": s_acc,
                "latency": latency,
                "error": False
            })

        except requests.exceptions.ConnectionError:
            print(f"  ❌ Could not connect to {API_URL}. Is the server running?")
            sys.exit(1)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append({
                "id": qid, "query": query,
                "product_accuracy": 0, "stock_accuracy": 0,
                "latency": 0, "error": True
            })

        print()

        # Rate limit: wait between queries to avoid Groq API throttling
        if test != tests[-1]:
            print(f"  ⏳ Waiting {QUERY_DELAY}s before next query (Groq rate limit)...")
            time.sleep(QUERY_DELAY)

    # ── Summary ──
    successful = [r for r in results if not r["error"]]
    failed = [r for r in results if r["error"]]

    if not successful:
        print("❌ No successful queries. Check the API server.")
        return

    avg_product_acc = sum(r["product_accuracy"] for r in successful) / len(successful)
    avg_stock_acc = sum(r["stock_accuracy"] for r in successful) / len(successful)
    avg_latency = sum(r["latency"] for r in successful) / len(successful)
    max_latency = max(r["latency"] for r in successful)
    min_latency = min(r["latency"] for r in successful)

    print(f"\n{'='*60}")
    print(f"  📊 EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Queries:        {len(results)}")
    print(f"  Successful:           {len(successful)}")
    print(f"  Failed/Errors:        {len(failed)}")
    print(f"  ─────────────────────────────────")
    print(f"  🎯 Avg Product Accuracy:  {avg_product_acc:.1f}%")
    print(f"  📦 Avg Stock Accuracy:    {avg_stock_acc:.1f}%")
    print(f"  ⏱️  Avg Latency:           {avg_latency:.2f}s")
    print(f"  ⏱️  Min Latency:           {min_latency:.2f}s")
    print(f"  ⏱️  Max Latency:           {max_latency:.2f}s")
    print(f"{'='*60}")

    # Save results to JSON
    report = {
        "total_queries": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "avg_product_accuracy": round(avg_product_acc, 1),
        "avg_stock_accuracy": round(avg_stock_acc, 1),
        "avg_latency_seconds": round(avg_latency, 2),
        "min_latency_seconds": round(min_latency, 2),
        "max_latency_seconds": round(max_latency, 2),
        "per_query_results": results
    }

    report_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  💾 Full results saved to {report_path}\n")


if __name__ == "__main__":
    run_evaluation()
