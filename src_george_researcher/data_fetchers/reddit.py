"""
Reddit sentiment fetching - no API key required.
Uses Reddit's public JSON API.
"""
import httpx
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone


@dataclass(frozen=True)
class RedditPost:
    """Single Reddit post with metadata."""
    title: str
    subreddit: str
    score: int
    num_comments: int
    url: str
    created_utc: str
    selftext: str


@dataclass(frozen=True)
class RedditSentiment:
    """Aggregated Reddit sentiment for a symbol."""
    symbol: str
    posts: list[RedditPost]
    total_mentions: int
    total_score: int
    avg_score: float
    top_subreddits: list[str]


# Subreddits to search for stock discussion
STOCK_SUBREDDITS = [
    "wallstreetbets",
    "stocks",
    "investing",
    "stockmarket",
    "options",
]


def _format_timestamp(utc_timestamp: float) -> str:
    """Convert UTC timestamp to readable date."""
    try:
        dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "Unknown"


def _extract_search_terms(company_name: str) -> list[str]:
    """Extract useful search terms from company name."""
    if not company_name:
        return []

    # Common suffixes to remove for better search
    suffixes = [
        ", Inc.", ", Inc", " Inc.", " Inc", " Corporation", " Corp.", " Corp",
        " Company", " Co.", " Co", " Ltd.", " Ltd", " Limited", " LLC", " L.P.",
        " PLC", " plc", " N.V.", " S.A.", " AG", " SE", " Group", " Holdings",
    ]

    name = company_name
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Also try to get first significant word for brands
    # e.g., "Apple Inc." -> ["Apple"]
    terms = [name]

    # If name has multiple words, the first word might be the brand
    words = name.split()
    if len(words) > 1 and len(words[0]) > 2:
        terms.append(words[0])

    return list(set(terms))


def fetch_reddit_sentiment(
    symbol: str,
    limit: int = 10,
    time_filter: str = "week",
    company_name: str = "",
) -> tuple[Optional[RedditSentiment], Optional[str]]:
    """
    Fetch Reddit posts mentioning a stock symbol or company name.

    Args:
        symbol: Stock ticker (e.g., "AAPL")
        limit: Max posts to fetch per subreddit
        time_filter: "day", "week", "month", "year", "all"
        company_name: Full company name for better search (e.g., "Apple Inc.")

    Returns:
        Tuple of (RedditSentiment or None, error message or None)
    """
    all_posts = []
    subreddit_counts: dict[str, int] = {}
    seen_urls: set[str] = set()  # Deduplicate posts

    headers = {
        "User-Agent": "George-Financial-Researcher/1.0"
    }

    # Build search queries: symbol + company name variations
    search_queries = [symbol]
    if company_name:
        search_queries.extend(_extract_search_terms(company_name))

    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            for subreddit in STOCK_SUBREDDITS:
                for query in search_queries:
                    try:
                        # Search within each subreddit
                        url = f"https://www.reddit.com/r/{subreddit}/search.json"
                        params = {
                            "q": query,
                            "restrict_sr": "true",
                            "sort": "relevance",
                            "t": time_filter,
                            "limit": limit,
                        }

                        response = client.get(url, params=params)

                        if response.status_code == 429:
                            # Rate limited, skip this query
                            continue

                        if response.status_code != 200:
                            continue

                        data = response.json()
                        posts = data.get("data", {}).get("children", [])

                        for post_wrapper in posts:
                            post = post_wrapper.get("data", {})
                            post_url = f"https://reddit.com{post.get('permalink', '')}"

                            # Skip duplicates (same post found via different search terms)
                            if post_url in seen_urls:
                                continue

                            # Filter: must mention symbol OR company name
                            title = post.get("title", "")
                            selftext = post.get("selftext", "")
                            content = (title + " " + selftext).upper()

                            # Check if any search term matches
                            matches = symbol.upper() in content
                            if not matches and company_name:
                                for term in _extract_search_terms(company_name):
                                    if term.upper() in content:
                                        matches = True
                                        break

                            if not matches:
                                continue

                            seen_urls.add(post_url)
                            all_posts.append(RedditPost(
                                title=title[:200],
                                subreddit=subreddit,
                                score=post.get("score", 0),
                                num_comments=post.get("num_comments", 0),
                                url=post_url,
                                created_utc=_format_timestamp(post.get("created_utc", 0)),
                                selftext=selftext[:300] if selftext else "",
                            ))

                            subreddit_counts[subreddit] = subreddit_counts.get(subreddit, 0) + 1

                    except Exception:
                        # Skip failed queries
                        continue

        if not all_posts:
            search_desc = f"{symbol}" + (f" / {company_name}" if company_name else "")
            return (None, f"No Reddit posts found for {search_desc}")

        # Sort by score (engagement)
        all_posts.sort(key=lambda p: p.score, reverse=True)
        all_posts = all_posts[:limit * 2]  # Keep top posts across all subreddits

        total_score = sum(p.score for p in all_posts)
        avg_score = total_score / len(all_posts) if all_posts else 0

        # Top subreddits by mention count
        top_subs = sorted(subreddit_counts.keys(), key=lambda s: subreddit_counts[s], reverse=True)[:3]

        return (
            RedditSentiment(
                symbol=symbol,
                posts=all_posts,
                total_mentions=len(all_posts),
                total_score=total_score,
                avg_score=avg_score,
                top_subreddits=top_subs,
            ),
            None,
        )

    except httpx.TimeoutException:
        return (None, "Reddit request timed out")
    except Exception as e:
        return (None, f"Reddit error: {str(e)}")


def format_reddit_report(sentiment: RedditSentiment) -> str:
    """
    Format Reddit sentiment as a report string for LLM agents.
    """
    lines = [
        f"Reddit Sentiment for {sentiment.symbol}",
        "-" * 30,
        "",
        f"Total Mentions: {sentiment.total_mentions}",
        f"Engagement: {sentiment.total_score} upvotes",
        f"Avg Score: {sentiment.avg_score:.1f}",
        f"Top Subreddits: {', '.join(sentiment.top_subreddits)}",
        "",
        "Top Discussions:",
    ]

    for i, post in enumerate(sentiment.posts[:7], 1):
        engagement = "[hot]" if post.score > 100 else "[+]" if post.score > 10 else "[o]"
        lines.append(f"{i}. {engagement} r/{post.subreddit}: {post.title}")
        lines.append(f"   Score: {post.score} | Comments: {post.num_comments} | {post.created_utc}")
        if post.selftext:
            preview = post.selftext[:100].replace('\n', ' ')
            lines.append(f"   {preview}...")
        lines.append("")

    lines.append("Retail Indicators:")
    if sentiment.avg_score > 50:
        lines.append("- High engagement, strong retail interest")
    elif sentiment.avg_score > 10:
        lines.append("- Moderate retail discussion")
    else:
        lines.append("- Low retail engagement")

    if "wallstreetbets" in sentiment.top_subreddits:
        lines.append("- Active on WallStreetBets (meme stock potential)")

    return "\n".join(lines)
