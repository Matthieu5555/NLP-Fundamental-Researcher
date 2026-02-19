# News Search Refactoring Plan

## Current Limitations

### 1. Generic Search Queries
The current Gemini search uses generic queries like:
```
"{symbol} {company_name} stock news latest developments"
```

This misses specialized, actionable research such as:
- Supply chain analysis ("Apple cobalt outlook", "Tesla battery supply chain")
- Input cost monitoring ("Steel prices impact on Ford")
- Regulatory developments ("Google antitrust EU timeline")
- Competitive dynamics ("Netflix vs Disney+ subscriber trends")

### 2. Missing Date Information
Gemini search results don't include publication dates. The `SearchResult` dataclass has:
```python
@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str
    score: float  # No date field
```

This makes it impossible to filter by recency or assess information freshness.

### 3. Narrow Scope
The current two-round search approach:
1. Round 1: Generic news search
2. Round 2: Topic-based follow-up (via `identify_research_topics()`)

While Round 2 improves specificity, it depends on what Round 1 found. If Round 1 misses a key angle, Round 2 won't catch it either.

## Desired Behavior

### 1. Multi-Angle Search Strategy
For each company, automatically generate searches across these dimensions:

**Core Business:**
- Recent news and developments
- Earnings and guidance updates
- Product launches and strategy changes

**Supply Chain & Inputs:**
- Key input commodities (auto -> steel, tech -> semiconductors)
- Supplier relationships and risks
- Geographic concentration

**Competitive Landscape:**
- Market share trends
- Competitor moves and pricing
- Industry consolidation

**Regulatory & Macro:**
- Regulatory actions (antitrust, tariffs, environmental)
- Macro factors (interest rates for REITs, oil for airlines)
- Geopolitical risks

**Sentiment & Positioning:**
- Analyst upgrades/downgrades
- Institutional positioning changes
- Short interest trends

### 2. Date-Aware Results
- Extract publication dates from search results
- Filter to last 90 days by default
- Weight more recent information higher
- Display dates in the UI

### 3. Relevance Scoring
Beyond Gemini's confidence score, apply domain-specific relevance:
- Direct company mentions vs. industry mentions
- Actionable information vs. commentary
- Primary sources vs. aggregators

## Implementation Ideas

### Phase 1: Company-Aware Queries
Build a mapping of companies to their key dependencies:

```python
COMPANY_DEPENDENCIES = {
    "AAPL": {
        "inputs": ["semiconductor supply", "display panels", "cobalt lithium"],
        "competitors": ["Samsung", "Google Pixel", "Huawei"],
        "regulatory": ["App Store antitrust", "EU DMA", "China relations"],
    },
    "TSLA": {
        "inputs": ["lithium prices", "battery cells", "charging infrastructure"],
        "competitors": ["BYD", "VW electric", "Rivian"],
        "regulatory": ["EV subsidies", "autonomous driving regulations"],
    },
}
```

For companies not in the mapping, use LLM to identify key dependencies.

### Phase 2: Search Orchestration
```python
async def multi_angle_search(symbol: str, company_name: str) -> List[SearchResult]:
    queries = [
        f"{company_name} news earnings guidance",
        f"{company_name} supply chain risks",
        f"{company_name} market share competition",
        f"{company_name} regulatory antitrust",
    ]

    # Add dependency-specific queries
    deps = COMPANY_DEPENDENCIES.get(symbol, {})
    for input_item in deps.get("inputs", []):
        queries.append(f"{input_item} outlook 2024 2025")

    # Run searches in parallel
    results = await asyncio.gather(*[search(q) for q in queries])

    # Deduplicate and rank
    return dedupe_and_rank(results)
```

### Phase 3: Date Extraction
Options for getting dates:
1. **Gemini response parsing**: Ask Gemini to include dates in its response
2. **URL fetching**: Fetch article pages and extract date metadata
3. **Heuristic extraction**: Parse dates from article titles/snippets

```python
def extract_date_from_result(result: SearchResult) -> Optional[datetime]:
    # Try common date patterns in title
    patterns = [
        r"(\d{1,2}/\d{1,2}/\d{4})",
        r"(January|February|...) \d{1,2}, \d{4}",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, result.title)
        if match:
            return parse_date(match.group(1))
    return None
```

### Phase 4: Integrated Due Diligence
Connect news search to the analysis pipeline:

```python
def identify_due_diligence_queries(bull_case: str, bear_case: str) -> List[str]:
    """Generate targeted searches to resolve bull/bear disagreements."""
    # Use LLM to identify specific factual questions
    prompt = f"""
    Given these bull and bear cases, identify 3-5 specific factual questions
    that would help resolve the key disagreements:

    BULL: {bull_case[:1500]}
    BEAR: {bear_case[:1500]}

    Return JSON array of search queries.
    """
    return llm_call(prompt)
```

## Priority: Future Enhancement

This refactor should be tackled after core functionality is stable.

## Files to Modify

- `src_george_researcher/data_fetchers/gemini_search.py` - Add date field, multi-query support
- `src_george_researcher/analysis_agents.py` - Enhance `identify_research_topics()`
- `src_george_researcher/orchestrator.py` - Integrate multi-angle search
- `src_george_researcher/analysis/us/orchestrator.py` - Same for US flow
- New file: `src_george_researcher/data_fetchers/company_dependencies.py` - Company mappings
