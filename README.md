# Issue Alert Automation Workflow

An event-driven automation platform that processes incoming incident alerts using **n8n** (workflow automation), **Python**, and **AWS Lambda**. When a webhook receives an alert, the system evaluates its priority, calculates a severity score, and routes it through conditional logic — high/critical alerts get processed by the Python API and trigger notifications, while lower-priority alerts are logged for review.

The backend runs on **AWS Lambda** behind API Gateway for serverless, low-latency processing, and can also run locally via FastAPI for development and testing.

## Architecture

```
                        ┌────────────────────────────────┐
                        │      n8n Workflow Engine        │
                        │                                │
┌──────────────┐        │  Webhook ──▶ Parse JSON        │
│ Event Source  │───────▶│      │                         │
│  (Webhook)   │        │      ▼                         │
└──────────────┘        │  IF priority == high/critical  │
                        │      │             │           │
                        │  ┌───▼───┐   ┌────▼────┐      │
                        │  │ TRUE  │   │  FALSE  │      │
                        │  └───┬───┘   └────┬────┘      │
                        └──────┼────────────┼───────────┘
                               │            │
                  ┌────────────▼──┐   ┌─────▼──────────┐
                  │  AWS Lambda   │   │  Log Alert     │
                  │  (Python API) │   │  (Low Priority)│
                  │               │   └─────┬──────────┘
                  │ ┌───────────┐ │         │
                  │ │Score Calc │ │         │
                  │ │Recommend  │ │         │
                  │ └───────────┘ │         │
                  └──────┬────────┘         │
                         │                  │
                  ┌──────▼────────┐         │
                  │ Format Slack  │         │
                  │ Notification  │         │
                  └──────┬────────┘         │
                         │                  │
                         └────────┬─────────┘
                                  │
                         ┌────────▼────────┐
                         │  Respond to     │
                         │  Webhook        │
                         └─────────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Workflow Engine | n8n | Visual automation, webhook handling, conditional routing |
| Backend API | Python + FastAPI | Alert processing, priority scoring |
| Serverless | AWS Lambda + API Gateway | Production deployment, low-latency processing |
| IaC | AWS SAM (template.yaml) | Infrastructure as Code for Lambda deployment |
| Containerization | Docker + Docker Compose | Running n8n locally |
| Data Format | JSON | All communication between services |
| API Style | REST | Webhook trigger + backend API calls |

## Project Structure

```
n8n/
├── backend/
│   ├── app.py                 # FastAPI application (local dev + Mangum adapter)
│   ├── lambda_handler.py      # Lambda entry point — FastAPI via Mangum
│   ├── lambda_standalone.py   # Lambda entry point — lightweight, no framework
│   └── requirements.txt       # Python dependencies
├── workflows/
│   └── issue_alert_workflow.json   # n8n workflow (importable)
├── tests/
│   ├── test_alerts.py         # Automated test suite
│   └── sample_payloads.json   # Example test payloads + curl commands
├── template.yaml              # AWS SAM template (Lambda + API Gateway)
├── docker-compose.yml         # n8n Docker setup
├── .gitignore
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- AWS CLI + SAM CLI (for Lambda deployment)

### Option A: Run Locally (Development)

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Start the server
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
# → {"status":"healthy","service":"issue-alert-processor"}
```

### Option B: Deploy to AWS Lambda

```bash
# Build and deploy with SAM
sam build
sam deploy --guided
```

SAM will:
1. Package the Python code into a Lambda deployment.
2. Create an API Gateway with `/process-alert` and `/health` endpoints.
3. Output the API Gateway URL for use in n8n.

After deployment, update the n8n HTTP Request node URL to point to the API Gateway endpoint.

### Start n8n

```bash
docker compose up -d
```

Open `http://localhost:5678`, import `workflows/issue_alert_workflow.json`, and activate the workflow.

### Run Tests

```bash
# From the project root
python tests/test_alerts.py
```

Send manual test alerts:

```bash
# High priority → routed to Python API
curl -X POST http://localhost:5678/webhook/issue-alert \
  -H "Content-Type: application/json" \
  -d '{
    "title": "API failure detected",
    "priority": "high",
    "source": "monitoring"
  }'
```

```bash
# Low priority → logged only
curl -X POST http://localhost:5678/webhook/issue-alert \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Minor UI glitch",
    "priority": "low",
    "source": "user_report"
  }'
```

## How the Workflow Works

### n8n Workflow Nodes

| # | Node | Type | What It Does |
|---|------|------|-------------|
| 1 | **Webhook Trigger** | Webhook | Listens for POST requests at `/webhook/issue-alert` |
| 2 | **Check Priority Level** | IF | Routes `high` priority to the Lambda/API path |
| 3 | **Check If Critical** | IF | Routes `critical` priority to the Lambda/API path |
| 4 | **Process Alert (Python API)** | HTTP Request | Calls the Lambda endpoint (or local FastAPI) |
| 5 | **Log Low Priority Alert** | Code | Creates structured log entry for medium/low alerts |
| 6 | **Format Slack Notification** | Code | Formats API response into Slack message |
| 7 | **Send Notification (Mock Slack)** | Code | Simulates Slack delivery |
| 8 | **Build Final Response** | Code | Assembles summary object |
| 9 | **Respond to Webhook** | Respond to Webhook | Returns JSON response to caller |

### Lambda Deployment Options

**`lambda_handler.py`** — Uses Mangum to run the full FastAPI app on Lambda. Best when you want feature parity between local and production.

**`lambda_standalone.py`** — Lightweight handler with zero framework dependencies. Processes API Gateway proxy events directly. Faster cold starts, smaller package size.

### Priority Scoring Logic

**Base score** (by priority level):
- `critical` → 100 | `high` → 80 | `medium` → 50 | `low` → 20

**Source multiplier** (by alert source):
- `security` → 1.5x | `monitoring` → 1.2x | `user_report` → 1.0x | `automated_test` → 0.8x

**Final score** = `base_score × source_multiplier` (capped at 100)

| Score | Recommendation |
|-------|---------------|
| 90+ | IMMEDIATE ACTION REQUIRED — Escalate to on-call engineer |
| 70–89 | HIGH PRIORITY — Investigate within 1 hour |
| 40–69 | MEDIUM PRIORITY — Schedule for next sprint |
| < 40 | LOW PRIORITY — Add to backlog |

## Example

**Request:**
```json
{
  "title": "API failure detected",
  "priority": "high",
  "source": "monitoring"
}
```

**Response:**
```json
{
  "status": "processed",
  "priority_score": 96.0,
  "recommendation": "IMMEDIATE ACTION REQUIRED - Escalate to on-call engineer",
  "processed_at": "2026-01-18T12:00:00.000000+00:00",
  "alert_id": "ALERT-20260118120000"
}
```

## Stopping Services

```bash
docker compose down          # stop n8n
# Ctrl+C in uvicorn terminal # stop local backend
```
