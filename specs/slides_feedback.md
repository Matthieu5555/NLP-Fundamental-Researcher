**TL;DR:** A unified IC deck that meets both the JPM modeling standards and MS research standards should run ~20-25 slides, structured as: (1) cover with recommendation and 3-second test, (2) investment thesis with bull/base/bear and what the market is missing, (3) company/industry overview, (4) financial model summary with key assumptions sourced and isolated, (5) valuation triangulation with football field, (6) risk/reward quantification, (7) catalyst timeline, (8) appendix with full model tables and checks. Every number traces back to a sourced assumption, every chart is annotated, and the narrative arc goes from "what to do" to "why" to "prove it."

---

Here's the full slide-by-slide structure, integrating both frameworks:

## Slide 1: Cover / Title

Ticker, exchange, sector, analyst name, date, version (following `[Company]_ICDeck_[YYYYMMDD]_v[X.X]_[Initials]` convention). Rating, current price, target price, implied upside/downside %, one-line falsifiable thesis, and a key financials snapshot table (EPS, P/E, EV/EBITDA, revenue, FCF yield for CY and next 2 years). Stock chart with event annotations. This is the 3-second test: if someone reads only this slide, they know what to do, why, and at what price.

## Slide 2: Investment Thesis

3-5 numbered, falsifiable pillars. Each one specific and testable. Below the pillars: a single paragraph on **what the market is missing**. If you cannot articulate the mispricing, the pitch has no reason to exist.

## Slide 3: Bull / Base / Bear Framework

Three-column table with price target, probability weight, probability-weighted expected value, key assumptions per case, and implied upside/downside from current price. Risk/reward ratio stated explicitly ("1.8:1 skew favoring upside"). Each scenario described in 1-2 sentences referencing specific assumptions, not vibes.

## Slide 4: Company Overview

What the company does in 2 paragraphs (generalist-readable). Revenue decomposition by segment/geography/customer type with a waterfall or stacked bar. Business model diagram showing how a dollar of revenue flows through the P&L, with fixed/variable cost split noted.

## Slide 5: Competitive Positioning

Market share data with sources and dates. Competitive moat assessment using a concrete framework (switching costs quantified, not "high barriers to entry"). 2x2 positioning chart against key peers on relevant axes. Management quality: ROIC vs. WACC track record, guidance hit rate, insider ownership, comp alignment.

## Slide 6: Industry Dynamics

TAM/SAM/SOM with methodology disclosed. Key growth drivers and headwinds, quantified. Supply/demand dynamics: capacity utilization, order backlogs, pricing trends. Regulatory environment with probability and timeline. Every data point sourced (publication, date, page reference per JPM convention).

## Slide 7-8: Financial Summary - Historical + Projected

Income Statement, Balance Sheet, Cash Flow Statement in condensed format. 3-5 years historical (FY20XXA) + 3-5 years projected (FY20XXE). Key margins highlighted (gross, EBITDA, EBIT, net). FCF explicitly defined (your definition stated). Net debt/EBITDA, current ratio, FCF yield. YoY growth rates for revenue and EPS. Sign conventions consistent and documented. Brackets for negatives, currency signs only at top/bottom, "NM" for meaningless ratios.

## Slide 9: Key Assumptions Table

Every driver isolated in one table: revenue growth by segment, margin trajectory, CapEx as % of revenue, working capital days, tax rate, share count. For each assumption: base/bull/bear value, source with page reference (`2025 AR Note 12 P73`), rationale, last updated. This mirrors the JPM Assumptions tab philosophy: nothing buried in formulas, everything auditable.

## Slide 10: EPS Bridge

Waterfall chart decomposing EPS from current year to target year: revenue growth contribution, margin expansion, operating leverage, share buybacks, tax changes, below-the-line items. This makes your thesis tangible by showing exactly where the earnings growth comes from.

## Slide 11: Your Estimates vs. Consensus

Revenue, EBITDA, EPS vs. Bloomberg/FactSet consensus for next 2-3 years. Variance column with explanation for each delta. Earnings revision trend (consensus moving up or down). Beat/miss history over last 8-12 quarters. What is currently priced in at the current multiple.

## Slide 12-13: Valuation

**Slide 12 - DCF:** WACC build with every component sourced (risk-free rate, beta methodology, ERP, cost of debt, capital structure). Terminal value via both perpetuity growth and exit multiple as crosscheck. Two-variable sensitivity table (WACC vs. terminal growth) with conditional formatting (green/yellow/red).

**Slide 13 - Relative Valuation:** Peer group defined and justified. Comps table: name, ticker, market cap, EV, relevant multiples, growth, margins. Premium/discount to peers with specific reasoning. Transaction comps if M&A relevant. SOTP if conglomerate.

## Slide 14: Football Field

Single horizontal bar chart triangulating all valuation approaches: DCF range, trading comps range, transaction comps range, 52-week range, analyst PT range. Current price marked. Implied assumptions check: "Our 22x target P/E implies X% long-term growth; here's why that's reasonable." Reverse DCF result: what growth the current price is implying.

## Slide 15: Risk Analysis (Quantified)

No generic disclaimers. Each risk specific and quantified: "Every $10/bbl in Brent impacts EBITDA by ~$150M or ~8%." Customer concentration, regulatory exposure, FX sensitivity, litigation, key man risk, all with scenario impact. ESG risks only if material to the business model. Explicit statement: "What would make us wrong" with falsifiable conditions for downgrade.

## Slide 16: Catalyst Timeline

Visual Gantt-style timeline of upcoming events: earnings dates, product launches, regulatory decisions, contract renewals, investor days, index rebalancing, lock-up expirations. For each: expected date, your expected outcome vs. consensus, and estimated stock impact if right/wrong.

## Slide 17: Monitoring Framework

3-5 KPIs to track that confirm or deny the thesis over the next 6-12 months, with specific thresholds. "If gross margin falls below 42% for two consecutive quarters, the thesis is broken." This gives the IC a built-in accountability framework.

## Slide 18: Recommendation Summary

Restate: rating, price target, risk/reward ratio, top 3 thesis pillars, biggest risk, nearest catalyst. One-paragraph conclusion. This slide should be a self-contained decision document.

## Appendix Slides (19+)

- Full quarterly financial model tables
- Detailed comps table
- WACC calculation detail
- Working capital build
- Debt schedule and maturity profile
- D&A / PP&E schedule
- Tax schedule
- Share count bridge (basic to diluted via treasury stock method)
- Management bios with track record
- Glossary if sector-specific
- Model integrity checks summary: balance sheet balances, cash flow reconciliation, debt rollforward, RE rollforward (all showing "OK" / "ERROR" status per the JPM checks framework)
- Source list with full citations

---

Want me to build this as a `.pptx` template?