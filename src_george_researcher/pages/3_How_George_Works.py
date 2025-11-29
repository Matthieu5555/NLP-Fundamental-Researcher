"""
How George Works - Methodology overview
"""
import streamlit as st

st.set_page_config(
    page_title="How George Works",
    page_icon="G",
    layout="wide",
)

st.title("How George Works")

st.markdown("""
George is your research assistant, not your advisor. He gathers data, runs analysis, and presents findings - you make the decisions.

---

## What George Does

**1. Collects Data**
- Stock fundamentals from Yahoo Finance
- SEC 10-K annual filings
- News sentiment from EODHD/Alpha Vantage
- Reddit discussions (r/wallstreetbets, r/stocks, etc.)
- Breaking news via web search

**2. Runs Analysis Agents**
Each agent specializes in one area and sees all the sentiment data:

| Agent | Focus |
|-------|-------|
| Fundamentals | Valuation, profitability, growth, balance sheet |
| Technicals | Trend, momentum, support/resistance, volume |
| Bull Case | Growth catalysts, competitive advantages |
| Bear Case | Risks, valuation concerns, competitive threats |
| Moat | Economic moat using Buffett's framework |
| SWOT | Strengths, weaknesses, opportunities, threats |

**3. Synthesizes Research**
A final summary pulls everything together - but without a recommendation. That's your job.

---

## The Philosophy

George uses a **Probability x Impact** risk framework:
- High probability + High impact = Flag immediately
- Low probability + High impact = Note as tail risk
- High probability + Low impact = Monitor

The bear case gets extra attention. Missing a risk is worse than missing upside.

---

## Data Sources

All analysis cites sources. The "All Sources" tab shows:
- Yahoo Finance stock data
- SEC EDGAR filings with direct links
- Individual news articles with sentiment scores
- Reddit posts with engagement metrics

---

## Limitations

- News APIs have some lag on breaking events
- LLMs can make reasoning errors
- Fundamentals reflect past quarters
- This is research, not financial advice

Always verify important findings before making decisions.
""")
