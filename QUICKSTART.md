# George Financial Analyst v2.0 - Quick Start Guide

## Overview

This guide will get you up and running with the new conversational financial analyst platform.

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm or yarn

## Setup (5 minutes)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your API keys
# Required: OPENROUTER_API_KEY
# Optional: ALPHA_VANTAGE_API_KEY, EODHD_API_KEY, TAVILY_API_KEY
```

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cp .env.example .env
# Default VITE_API_URL=http://localhost:5000 is fine for development
```

## Running the Application

You need two terminal windows:

### Terminal 1: Backend (Flask)

```bash
cd backend
source venv/bin/activate  # If using venv
python app.py
```

The backend will start on http://localhost:5000

### Terminal 2: Frontend (React)

```bash
cd frontend
npm run dev
```

The frontend will start on http://localhost:5173

## Using the Application

1. **Open browser** to http://localhost:5173

2. **Enter a stock ticker** (e.g., AAPL, MSFT, GOOGL)

3. **Click "Analyze Stock"**
   - Initial analysis will run (mock data for now)
   - Progress updates will stream in real-time

4. **Browse analysis results**
   - Click tabs to view different sections
   - Fundamentals, Technicals, Bull Case, Bear Case, etc.

5. **Scroll down to chat**
   - Ask questions about the analysis
   - Example: "What is the return on equity?"
   - AI responses stream in real-time

6. **Download report**
   - Click "Download Report" to save as markdown

## Architecture

### One-Page Flow

```
┌─────────────────────────────────┐
│  Stock Picker                   │  ← Enter ticker
└─────────────────────────────────┘
           ↓ (after submit)
┌─────────────────────────────────┐
│  Analysis View (Tabbed)         │  ← Read initial analysis
│  - Fundamentals                 │
│  - Technicals                   │
│  - Bull/Bear Cases              │
│  - Competitive Moat             │
└─────────────────────────────────┘
           ↓ (scroll down)
┌─────────────────────────────────┐
│  Chat Interface                 │  ← Ask questions
│  - Q&A with AI                  │
│  - Streaming responses          │
└─────────────────────────────────┘
```

All on a single scrollable page with sticky header.

## API Endpoints (for testing)

### Analysis

```bash
# Create session
curl -X POST http://localhost:5000/api/analysis/start \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL"}'

# Get session status
curl http://localhost:5000/api/analysis/{session_id}/status

# Run analysis (SSE stream)
curl http://localhost:5000/api/analysis/{session_id}/run

# List sessions
curl http://localhost:5000/api/analysis/sessions
```

### Chat

```bash
# Stream chat (SSE)
curl "http://localhost:5000/api/chat/stream?session_id={id}&message=What%20is%20the%20PE%20ratio"

# Get conversation history
curl http://localhost:5000/api/chat/{session_id}/history

# Get beliefs
curl http://localhost:5000/api/chat/{session_id}/beliefs
```

### Reports

```bash
# Get report (JSON)
curl http://localhost:5000/api/reports/{session_id}

# Get report (Markdown)
curl "http://localhost:5000/api/reports/{session_id}?format=markdown"

# Get sections
curl http://localhost:5000/api/reports/{session_id}/sections

# Export PDF (placeholder)
curl -X POST http://localhost:5000/api/reports/{session_id}/export/pdf
```

## Current Status (MVP)

### What Works

- Backend API with session management
- SSE streaming for real-time updates
- Belief graph system (NetworkX)
- Dynamic report builder
- Frontend one-page layout
- Stock picker component
- Tabbed analysis view
- Chat interface with streaming

### What's Mocked (TODO: Integration)

- Initial analysis uses placeholder data
- Chat responses are mock (not using OpenRouter yet)
- No actual data fetching (yfinance, news, etc.)
- No belief extraction from conversation
- PDF export returns text file

## Next Steps

### To get real analysis working:

1. **Integrate existing agents**:
   ```python
   # In backend/api/analysis.py:run_initial_analysis()
   from agents.orchestrator import run_analysis
   results = run_analysis(ticker, options)
   ```

2. **Connect OpenRouter**:
   ```python
   # In backend/api/chat.py:stream_chat()
   from agents.llm import get_llm_response_stream
   for token in get_llm_response_stream(message, context):
       yield f"data: {token}\n\n"
   ```

3. **Add belief extraction**:
   ```python
   # Create backend/core/belief_extraction.py
   def extract_beliefs(conversation, session):
       # Use LLM to detect user beliefs
       # Update session.belief_graph
   ```

## Troubleshooting

### Backend won't start

- Check Python version: `python --version` (need 3.11+)
- Install dependencies: `pip install -r requirements.txt`
- Check .env file exists

### Frontend won't start

- Check Node version: `node --version` (need 18+)
- Clear node_modules: `rm -rf node_modules && npm install`
- Check .env file has correct API URL

### CORS errors

- Ensure backend is running on port 5000
- Check CORS_ORIGINS in backend/.env
- Try restarting both servers

### SSE not working

- Check browser console for errors
- Verify EventSource is supported (all modern browsers)
- Test endpoint with curl first

## Development Tips

### Hot reload

Both frontend and backend support hot reload:
- Frontend: Changes to .jsx files auto-refresh
- Backend: Flask debug mode auto-restarts (set FLASK_ENV=development)

### Testing without frontend

Use curl or Postman to test API endpoints directly.

### Viewing session data

Check session state in Python debugger or add print statements in backend/core/session.py

## Production Deployment (Future)

- Frontend: Deploy to Vercel/Netlify
- Backend: Deploy to Railway/Render/AWS
- Database: Migrate session storage to Redis
- Monitoring: Add error tracking (Sentry)

---

For detailed architecture, see ARCHITECTURE.md
For progress tracking, see PROGRESS.md
