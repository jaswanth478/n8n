"""
Standalone AWS Lambda handler (no framework dependency).

Lightweight alternative that processes alerts directly without FastAPI.
Suitable for single-purpose Lambda functions behind API Gateway.
"""

import json
from datetime import datetime, timezone

PRIORITY_SCORES = {
    "critical": 100,
    "high": 80,
    "medium": 50,
    "low": 20,
}

SOURCE_WEIGHT = {
    "monitoring": 1.2,
    "security": 1.5,
    "user_report": 1.0,
    "automated_test": 0.8,
}

VALID_PRIORITIES = set(PRIORITY_SCORES.keys())


def calculate_priority_score(priority: str, source: str) -> float:
    base_score = PRIORITY_SCORES.get(priority, 30)
    multiplier = SOURCE_WEIGHT.get(source, 1.0)
    return round(min(base_score * multiplier, 100), 1)


def get_recommendation(score: float) -> str:
    if score >= 90:
        return "IMMEDIATE ACTION REQUIRED - Escalate to on-call engineer"
    elif score >= 70:
        return "HIGH PRIORITY - Investigate within 1 hour"
    elif score >= 40:
        return "MEDIUM PRIORITY - Schedule for next sprint"
    return "LOW PRIORITY - Add to backlog"


def build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    """AWS Lambda entry point for API Gateway proxy integration."""
    try:
        path = event.get("path", "") or event.get("rawPath", "")
        method = event.get("httpMethod", "") or event.get("requestContext", {}).get("http", {}).get("method", "")

        if path == "/health" and method == "GET":
            return build_response(200, {
                "status": "healthy",
                "service": "issue-alert-processor",
                "runtime": "aws-lambda",
            })

        if path == "/process-alert" and method == "POST":
            body = event.get("body", "{}")
            if isinstance(body, str):
                body = json.loads(body)

            title = body.get("title", "")
            priority = body.get("priority", "")
            source = body.get("source", "unknown")

            if not title or not title.strip():
                return build_response(422, {"detail": "title is required"})
            if priority not in VALID_PRIORITIES:
                return build_response(422, {
                    "detail": f"priority must be one of: {', '.join(VALID_PRIORITIES)}"
                })

            score = calculate_priority_score(priority, source)
            recommendation = get_recommendation(score)
            now = datetime.now(timezone.utc)

            return build_response(200, {
                "status": "processed",
                "priority_score": score,
                "recommendation": recommendation,
                "processed_at": now.isoformat(),
                "alert_id": f"ALERT-{now.strftime('%Y%m%d%H%M%S')}",
            })

        return build_response(404, {"detail": f"Not found: {method} {path}"})

    except json.JSONDecodeError:
        return build_response(400, {"detail": "Invalid JSON in request body"})
    except Exception as e:
        return build_response(500, {"detail": f"Internal error: {str(e)}"})
