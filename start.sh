#!/bin/bash

# George Financial Analyst - Startup Script

echo "==================================="
echo "George Financial Analyst v2.0"
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

echo "Starting backend server on port 5001..."
cd backend
PORT=5001 uv run python app.py &
BACKEND_PID=$!
cd ..

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
