#!/bin/bash
# AnalyticsIQ - Start backend server
# Single backend on port 8000 handles both Claude and Ollama models

echo "Starting AnalyticsIQ backend on port 8000..."

# Check if Ollama is running
if curl -s --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  Ollama detected - local models enabled"
else
    echo "  Ollama not running - local models disabled"
    echo "  To enable: ollama serve"
fi

# Start backend
cd "$(dirname "$0")/backend"
python -m uvicorn app.main:app --reload --port 8000
