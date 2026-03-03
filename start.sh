#!/bin/bash

# George Research - Startup Script

echo "==================================="
echo "George Research v2.1"
echo "FastAPI + Dual Job Queue"
echo "==================================="
echo ""

# ── Environment setup ──────────────────────────────────────────────────

if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env from template..."
    cp backend/.env.example backend/.env
    echo ""
    echo "  backend/.env created. Please add your API keys (see below)."
    echo ""
fi

if [ ! -f "frontend_v2/.env" ]; then
    echo "Creating frontend_v2/.env..."
    echo "VITE_API_URL=http://localhost:5001" > frontend_v2/.env
fi

# ── API key validation ─────────────────────────────────────────────────

# Source the .env file to read key values (without exporting to current shell permanently)
OPENROUTER_KEY=$(grep -E '^OPENROUTER_API_KEY=' backend/.env | cut -d'=' -f2-)
GOOGLE_KEY=$(grep -E '^GOOGLE_API_KEY=' backend/.env | cut -d'=' -f2-)

# Treat placeholder values as empty
PLACEHOLDERS="your_key_here your_google_api_key_here"
for ph in $PLACEHOLDERS; do
    [ "$OPENROUTER_KEY" = "$ph" ] && OPENROUTER_KEY=""
    [ "$GOOGLE_KEY" = "$ph" ] && GOOGLE_KEY=""
done

HAS_ERROR=false

echo "API Keys"
echo "-----------------------------------"

# OpenRouter (required)
if [ -z "$OPENROUTER_KEY" ]; then
    echo "  OPENROUTER_API_KEY    MISSING (required)"
    echo "    Powers all LLM analysis and chat."
    echo "    Get a key: https://openrouter.ai/keys"
    echo ""
    HAS_ERROR=true
else
    echo "  OPENROUTER_API_KEY    OK"
fi

# Google Gemini (recommended)
if [ -z "$GOOGLE_KEY" ]; then
    echo "  GOOGLE_API_KEY        MISSING (recommended)"
    echo "    Enables real-time news search via Gemini grounding."
    echo "    Get a key: https://aistudio.google.com/apikey"
else
    echo "  GOOGLE_API_KEY        OK"
fi

echo "-----------------------------------"
echo ""

if [ "$HAS_ERROR" = true ]; then
    echo "Edit backend/.env and add the required key(s), then re-run ./start.sh"
    exit 1
fi

# ── Start servers ──────────────────────────────────────────────────────

echo "Starting FastAPI backend server on port 5001..."
echo "  - US Queue: 3 workers (FinancialDatasets.ai)"
echo "  - Non-US Queue: 2 workers (Alpha Vantage)"
echo ""
DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH" uv run uvicorn backend.main:app --host 0.0.0.0 --port 5001 &
BACKEND_PID=$!

echo "Waiting for backend to start..."
sleep 3

echo ""
echo "Starting frontend server..."
cd frontend_v2
npm run dev -- --port 5174 &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "READY!"
echo "==================================="
echo ""
echo "Frontend: http://localhost:5174"
echo "Backend:  http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
