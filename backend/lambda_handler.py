"""
AWS Lambda handler for the Issue Alert Processor.

Uses Mangum to adapt the FastAPI application for AWS Lambda + API Gateway.
This allows the same codebase to run both locally (uvicorn) and on Lambda.
"""

from mangum import Mangum
from app import app

handler = Mangum(app, lifespan="off")
