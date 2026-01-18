"""
Test script for the Issue Alert Automation Workflow.

Tests both the Python backend directly and the full n8n webhook pipeline.
Run with: python tests/test_alerts.py
"""

import requests
import json
import sys
import time

PYTHON_API_URL = "http://localhost:8000"
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/issue-alert"

TEST_PAYLOADS = [
    {
        "name": "High Priority - Monitoring Alert",
        "payload": {
            "title": "API failure detected",
            "priority": "high",
            "source": "monitoring",
            "description": "Main API endpoint returning 500 errors",
        },
        "expected_min_score": 70,
    },
    {
        "name": "Critical - Security Alert",
        "payload": {
            "title": "Unauthorized access attempt detected",
            "priority": "critical",
            "source": "security",
            "description": "Multiple failed login attempts from suspicious IP",
        },
        "expected_min_score": 90,
    },
    {
        "name": "Medium Priority - User Report",
        "payload": {
            "title": "Dashboard loading slowly",
            "priority": "medium",
            "source": "user_report",
            "description": "Users reporting slow page loads on dashboard",
        },
        "expected_min_score": 40,
    },
    {
        "name": "Low Priority - Automated Test",
        "payload": {
            "title": "Non-critical test flake in CI",
            "priority": "low",
            "source": "automated_test",
            "description": "Intermittent test failure in non-critical module",
        },
        "expected_min_score": 10,
    },
]


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_result(name, response_data, expected_min_score):
    score = response_data.get("priority_score", 0)
    status = response_data.get("status", "unknown")
    passed = score >= expected_min_score and status == "processed"
    icon = "PASS" if passed else "FAIL"

    print(f"\n  [{icon}] {name}")
    print(f"    Status:         {status}")
    print(f"    Priority Score: {score}/100 (expected >= {expected_min_score})")
    print(f"    Recommendation: {response_data.get('recommendation', 'N/A')}")
    print(f"    Alert ID:       {response_data.get('alert_id', 'N/A')}")
    return passed


def test_health_check():
    print_header("Health Check")
    try:
        resp = requests.get(f"{PYTHON_API_URL}/health", timeout=5)
        data = resp.json()
        healthy = data.get("status") == "healthy"
        print(f"  [{'PASS' if healthy else 'FAIL'}] Service: {data}")
        return healthy
    except requests.ConnectionError:
        print("  [FAIL] Cannot connect to Python backend at localhost:8000")
        print("         Start it with: uvicorn backend.app:app --reload")
        return False


def test_python_backend():
    print_header("Testing Python Backend Directly")
    results = []
    for test in TEST_PAYLOADS:
        try:
            resp = requests.post(
                f"{PYTHON_API_URL}/process-alert",
                json=test["payload"],
                timeout=5,
            )
            if resp.status_code == 200:
                passed = print_result(test["name"], resp.json(), test["expected_min_score"])
                results.append(passed)
            else:
                print(f"\n  [FAIL] {test['name']} - HTTP {resp.status_code}: {resp.text}")
                results.append(False)
        except requests.ConnectionError:
            print(f"\n  [FAIL] {test['name']} - Connection refused")
            results.append(False)
    return results


def test_n8n_webhook():
    print_header("Testing n8n Webhook Pipeline")
    payload = TEST_PAYLOADS[0]["payload"]
    try:
        resp = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
        print(f"  Status Code: {resp.status_code}")
        print(f"  Response: {json.dumps(resp.json(), indent=2)}")
        return resp.status_code == 200
    except requests.ConnectionError:
        print("  [SKIP] n8n not running at localhost:5678")
        print("         Start n8n with: docker-compose up -d")
        return None


def test_invalid_payload():
    print_header("Testing Error Handling")
    bad_payloads = [
        {"name": "Missing title", "payload": {"priority": "high", "source": "monitoring"}},
        {"name": "Invalid priority", "payload": {"title": "Test", "priority": "urgent", "source": "monitoring"}},
        {"name": "Empty payload", "payload": {}},
    ]
    results = []
    for test in bad_payloads:
        try:
            resp = requests.post(
                f"{PYTHON_API_URL}/process-alert",
                json=test["payload"],
                timeout=5,
            )
            rejected = resp.status_code == 422
            print(f"  [{'PASS' if rejected else 'FAIL'}] {test['name']} -> HTTP {resp.status_code}")
            results.append(rejected)
        except requests.ConnectionError:
            print(f"  [FAIL] {test['name']} - Connection refused")
            results.append(False)
    return results


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ISSUE ALERT AUTOMATION - TEST SUITE")
    print("=" * 60)

    all_passed = True

    if not test_health_check():
        print("\nBackend is not running. Start it first:")
        print("  cd backend && uvicorn app:app --reload")
        sys.exit(1)

    backend_results = test_python_backend()
    error_results = test_invalid_payload()
    webhook_result = test_n8n_webhook()

    passed = sum(backend_results) + sum(error_results)
    total = len(backend_results) + len(error_results)

    print_header("TEST SUMMARY")
    print(f"  Backend tests:  {sum(backend_results)}/{len(backend_results)} passed")
    print(f"  Error handling: {sum(error_results)}/{len(error_results)} passed")
    if webhook_result is not None:
        print(f"  n8n webhook:    {'PASS' if webhook_result else 'FAIL'}")
    else:
        print(f"  n8n webhook:    SKIPPED (n8n not running)")
    print(f"\n  Total: {passed}/{total} passed")

    sys.exit(0 if passed == total else 1)
