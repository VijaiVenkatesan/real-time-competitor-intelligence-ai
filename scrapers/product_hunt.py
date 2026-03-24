"""
Product Hunt RSS Scraper — zero cost, no API key, no account.
Uses Product Hunt's public RSS feed at producthunt.com/feed
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


def get_product_hunt_data(company_name: str) -> dict:
    result = {
        "source": "Product Hunt RSS (free, no key)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "products": [],
        "total_upvotes": 0,
        "most_recent_launch": None,
        "top_product": None,
        "error": None,
    }

    try:
        resp = requests.get(
            "https://www.producthunt.com/feed",
            headers={"User-Agent": "Mozilla/5.0 (compatible; CompetitorBot/1.0)"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        company_lower = company_name.lower()
        matched = []

        for item in items:
            title       = item.findtext("title", "")
            link        = item.findtext("link", "")
            pub_date    = item.findtext("pubDate", "")
            description = item.findtext("description", "")
            searchable  = (title + " " + description).lower()
            if company_lower not in searchable:
                continue
            clean_desc = re.sub(r"<[^>]+>", "", description).strip()[:250]
            votes = 0
            m = re.search(r"(\d+)\s*(?:upvotes?|votes?)", searchable)
            if m:
                votes = int(m.group(1))
            matched.append({
                "name": title,
                "tagline": clean_desc[:100],
                "description": clean_desc,
                "votes": votes,
                "launched_at": pub_date,
                "url": link,
            })

        result["products"] = matched
        result["total_upvotes"] = sum(p["votes"] for p in matched)
        if matched:
            result["top_product"] = max(matched, key=lambda x: x["votes"])
            result["most_recent_launch"] = matched[0]

        # Fallback: scrape PH search page
        if not matched:
            query = requests.utils.quote(company_name)
            r2 = requests.get(
                f"https://www.producthunt.com/search?q={query}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            names    = re.findall(r'"name"\s*:\s*"([^"]{5,80})"', r2.text)[:6]
            taglines = re.findall(r'"tagline"\s*:\s*"([^"]{5,120})"', r2.text)
            urls     = re.findall(r'"url"\s*:\s*"(https://www\.producthunt\.com/posts/[^"]+)"', r2.text)
            for i, name in enumerate(names):
                matched.append({
                    "name": name,
                    "tagline": taglines[i] if i < len(taglines) else "",
                    "votes": 0,
                    "url": urls[i] if i < len(urls) else "",
                    "launched_at": "",
                })
            result["products"] = matched
            if matched:
                result["top_product"] = matched[0]
                result["most_recent_launch"] = matched[0]
                result["note"] = "From PH search page (limited data)"

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Product Hunt error: {e}")

    return result
