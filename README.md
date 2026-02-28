# George - AI Equity Research

AI-powered equity research platform. Runs multi-agent analysis (fundamentals, technicals, bull/bear debate, moat, strategy, valuation) on any public company, then lets you chat with the results and export PDF reports.

## Setup

Requires Python 3.13+, Node.js 18+, and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd george_researcher_js
cp backend/.env.example backend/.env    # add your API keys (OPENROUTER_API_KEY required)
./start.sh                              # starts backend on :5001, frontend on :5173
```

Open http://localhost:5173.

## Documentation

See [DOCS.md](./DOCS.md) for architecture, API reference, project structure, and configuration details.

## License

Private - All rights reserved
