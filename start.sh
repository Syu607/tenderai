#!/bin/bash

set -e

echo "====================================="
echo "Starting TenderAI Production Server"
echo "====================================="

# Go to project folder
cd /home/ubuntu/TenderAI

# Activate virtual environment
source venv/bin/activate

# Create required folders
mkdir -p backend/uploads/tenders
mkdir -p backend/uploads/bidders
mkdir -p reports

echo "Starting FastAPI..."

exec python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000