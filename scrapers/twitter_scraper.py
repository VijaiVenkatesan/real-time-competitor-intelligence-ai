"""
Reddit Mentions Scraper — replaces Twitter/X
Completely free. No API key. No account needed.
Uses Reddit's public JSON search API (no OAuth required for read-only search).
Searches across r/investing, r/technology, r/startups, r/business, r/stocks, etc.
"""

import requests
from datetime import datetime
import logging
from collections import Counter

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "CompetitorIntelligenceBot/1.0 (research tool)",
    "Accept": "application/json",
}

TARGET_SUBREDDITS = [
    "investing", "technology", "startups", "business",
    "stocks", "entrepreneur", "SaaS", "artificial", "programming",
]


def _search_reddit(query: str, subreddit: str | None = None, limit: int = 10) -> list[dict]:
    """Search Reddit posts mentioning a query."""
    posts = []
    try:
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
        else:
            url = "https://www.reddit.com/search.json"

        resp = requests.get(
            url,
            params={
                "q": query,
                "sort": "relevance",
                "t": "month",
                "limit": limit,
                "restrict_sr": "1" if subreddit else "0",
                "type": "link",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return posts

        data = resp.json()
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title", ""),
                "text": post.get("selftext", "")[:300],
                "subreddit": post.get("subreddit", ""),
                "score": post.get("score", 0),
                "upvote_ratio": post.get("upvote_ratio", 0),
                "num_comments": post.get("num_comments", 0),
                "created_utc": post.get("created_utc", 0),
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "author": post.get("author", ""),
            })
    except Exception as e:
        logger.debug(f"Reddit search error: {e}")
    return posts


def analyze_reddit_sentiment(posts: list[dict]) -> dict:
    positive_kw = ["great","love","amazing","best","excellent","awesome","growth",
                   "launch","innovative","impressed","strong","buy","bullish"]
    negative_kw = ["bad","terrible","awful","hate","worst","broken","fail","slow",
                   "expensive","avoid","bearish","scam","lawsuit","overrated"]

    pos = neg = neu = 0
    for p in posts:
        text = (p.get("title", "") + " " + p.get("text", "")).lower()
        has_pos = any(k in text for k in positive_kw)
        has_neg = any(k in text for k in negative_kw)
        if has_pos and not has_neg:
            pos += 1
        elif has_neg and not has_pos:
            neg += 1
        else:
            neu += 1

    total = pos + neg + neu
    return {
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "sentiment_label": "Positive" if pos > neg else ("Negative" if neg > pos else "Mixed/Neutral"),
        "positive_pct": round(pos / total * 100, 1) if total else 0,
        "negative_pct": round(neg / total * 100, 1) if total else 0,
    }


def get_twitter_mentions(company_name: str) -> dict:
    """
    Fetch Reddit mentions of a company (replaces Twitter/X scraper).
    Reddit's public JSON API requires no key.
    """
    result = {
        "source": "Reddit (free public API, no key)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "recent_tweets": [],   # kept for interface compatibility
        "total_scraped": 0,
        "sentiment": {},
        "top_tweets": [],      # kept for interface compatibility
        "subreddit_breakdown": {},
        "error": None,
    }

    all_posts: list[dict] = []

    # Global search first (most comprehensive)
    global_posts = _search_reddit(company_name, limit=20)
    all_posts.extend(global_posts)

    # Search a few targeted subreddits
    for sr in TARGET_SUBREDDITS[:4]:
        sr_posts = _search_reddit(company_name, subreddit=sr, limit=5)
        all_posts.extend(sr_posts)

    # Deduplicate by URL
    seen_urls: set[str] = set()
    unique_posts = []
    for p in all_posts:
        if p["url"] not in seen_urls:
            seen_urls.add(p["url"])
            unique_posts.append(p)

    result["total_scraped"] = len(unique_posts)
    result["recent_tweets"] = unique_posts  # interface compatibility

    # Top posts by score
    top = sorted(unique_posts, key=lambda x: x.get("score", 0), reverse=True)
    result["top_tweets"] = [
        {
            "text": p["title"],
            "likes": p["score"],
            "retweets": p["num_comments"],
            "date": str(datetime.fromtimestamp(p.get("created_utc", 0)).date()),
        }
        for p in top[:5]
    ]

    # Subreddit breakdown
    sr_counter = Counter(p.get("subreddit", "unknown") for p in unique_posts)
    result["subreddit_breakdown"] = dict(sr_counter.most_common(8))

    if unique_posts:
        result["sentiment"] = analyze_reddit_sentiment(unique_posts)
    else:
        result["error"] = "No Reddit posts found for this company"

    return result
