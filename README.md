# George Financial Analyst v2.0

A conversational AI-powered financial analysis platform. One-page interface for stock analysis with multi-agent AI and interactive chat.

## Quick Start

```bash
# 1. Setup
uv sync
cd frontend && npm install && cd ..

# 2. Configure
cp backend/.env.example backend/.env
# Edit backend/.env and add OPENROUTER_API_KEY

# 3. Run (two terminals)
# Terminal 1: PORT=5001 uv run python app.py  
# Terminal 2: cd frontend && npm run dev

# Or use: ./start.sh
```

Open http://localhost:5173

## Features

- Multi-agent analysis (fundamentals, technicals, bull/bear, moat, SWOT)
- Real-time streaming AI responses
- Conversational Q&A with belief tracking
- Dynamic report generation
- One-page scrollable interface

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Detailed setup
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [SETUP_COMPLETE.md](SETUP_COMPLETE.md) - What's integrated

Built with React, Flask, OpenRouter, yfinance, NetworkX, and FAISS.

MIT License - See full README in QUICKSTART.md
