"""
Issue Alert Automation - Python Backend

A FastAPI service that processes incoming issue alerts,
calculates priority scores, and returns structured responses
for the n8n automation workflow.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone

app = FastAPI(
    title="Issue Alert Processor",
    description="Backend service for the n8n Issue Alert Automation Workflow",
    version="1.0.0",
)

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


class AlertPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    priority: str = Field(..., pattern="^(critical|high|medium|low)$")
    source: str = Field(default="unknown")
    description: str = Field(default="")


class AlertResponse(BaseModel):
    status: str
    priority_score: float
    recommendation: str
    processed_at: str
    alert_id: str


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


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "issue-alert-processor"}


@app.post("/process-alert", response_model=AlertResponse)
def process_alert(alert: AlertPayload):
    try:
        score = calculate_priority_score(alert.priority, alert.source)
        recommendation = get_recommendation(score)
        now = datetime.now(timezone.utc)
        alert_id = f"ALERT-{now.strftime('%Y%m%d%H%M%S')}"

        return AlertResponse(
            status="processed",
            priority_score=score,
            recommendation=recommendation,
            processed_at=now.isoformat(),
            alert_id=alert_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/log-result")
def log_result(payload: dict):
    """Receives the final workflow result from n8n for logging."""
    print(f"[LOG] Workflow result received: {payload}")
    return {
        "status": "logged",
        "message": "Result recorded successfully",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
