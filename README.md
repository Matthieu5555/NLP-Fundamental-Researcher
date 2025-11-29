# George - Your Financial Researcher

AI-powered stock analysis using multiple specialized agents for comprehensive investment research.

## Quick Start

```bash
# Install dependencies
uv sync

# Set your API key
echo "OPENROUTER_API_KEY=your_key_here" > .env

# Run the app
uv run python -m streamlit run src_george_researcher/app.py
```

## Features

- **Fundamental Analysis Agent**: Evaluates valuation, profitability, growth, and financial health
- **Technical Analysis Agent**: Analyzes price trends, momentum indicators, and key levels
- **Bull Case Agent**: Argues the investment case with growth catalysts and competitive advantages
- **Bear Case Agent**: Presents risks, valuation concerns, and competitive threats
- **Moat Analysis Agent**: Warren Buffett-style competitive advantage evaluation
- **SWOT Specialist Agent**: Traditional strategic analysis of strengths, weaknesses, opportunities, and threats
- **George's Overall Recommendation**: Synthesizes all analysis into a final BUY/HOLD/SELL decision

## Data Sources

All market data comes from Yahoo Finance (free, no API key needed):
- Real-time stock prices and fundamentals
- Historical price data for technical analysis
- Company profiles and financial statements

## Configuration

Create a `.env` file:

```
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=anthropic/claude-3-haiku  # default
```

## Requirements

- Python 3.11+
- OpenRouter API key (for LLM analysis)
