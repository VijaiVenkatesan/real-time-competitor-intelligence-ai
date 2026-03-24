"""
Google News RSS Scraper — replaces NewsAPI
Completely free. No API key. No account. Works on Streamlit Cloud.
Uses Google News RSS feed (publicly available).
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


def get_company_news(company_name: str, max_articles: int = 20) -> dict:
    """
    Fetch latest news via Google News RSS — zero cost, no key required.
    """
    result = {
        "source": "Google News RSS (free, no key)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "total_results": 0,
        "articles": [],
        "sentiment_summary": None,
        "error": None,
    }

    query = requests.utils.quote(f'"{company_name}"')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CompetitorBot/1.0)"},
            timeout=15,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            result["error"] = "Empty RSS feed"
            return result

        items = channel.findall("item")
        result["total_results"] = len(items)
        articles = []

        for item in items[:max_articles]:
            title = item.findtext("title", "")
            link  = item.findtext("link", "")
            pub   = item.findtext("pubDate", "")
            desc  = item.findtext("description", "")

            # Google News encodes source in title as "Title - Source"
            source_name = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source_name = parts[1].strip()

            clean_desc = re.sub(r"<[^>]+>", "", desc).strip()[:300]

            articles.append({
                "title": title,
                "description": clean_desc,
                "source": source_name,
                "published_at": pub,
                "url": link,
            })

        result["articles"] = articles

        # Keyword-based sentiment scoring
        positive_kw = ["growth", "profit", "launch", "partnership", "funding",
                       "innovation", "expands", "wins", "record", "raises", "acquires"]
        negative_kw = ["lawsuit", "layoff", "decline", "loss", "scandal", "breach",
                       "drops", "fired", "investigation", "fine", "crash", "cuts"]
        pos = neg = 0
        for a in articles:
            text = (a["title"] + " " + a["description"]).lower()
            pos += sum(1 for k in positive_kw if k in text)
            neg += sum(1 for k in negative_kw if k in text)

        total = pos + neg
        label = "Neutral"
        if total > 0:
            score = (pos - neg) / total
            label = "Positive" if score > 0.2 else ("Negative" if score < -0.2 else "Neutral")

        result["sentiment_summary"] = {
            "label": label,
            "positive_signals": pos,
            "negative_signals": neg,
        }

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Google News RSS error for {company_name}: {e}")

    return result
