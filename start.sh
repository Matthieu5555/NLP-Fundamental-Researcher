#!/bin/bash

# Constant - Your Intern - Startup Script

echo "==================================="
echo "Constant - Your Intern v2.1"
echo "FastAPI + Dual Job Queue"
echo "==================================="
echo ""

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env from template..."
    cp backend/.env.example backend/.env
    echo "Please edit backend/.env and add your OPENROUTER_API_KEY"
    exit 1
fi

if [ ! -f "frontend/.env" ]; then
    echo "Creating frontend/.env..."
    echo "VITE_API_URL=http://localhost:5001" > frontend/.env
fi

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
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "==================================="
echo "READY!"
echo "==================================="
echo ""
echo "Frontend: http://localhost:5173"
echo "Backend:  http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
