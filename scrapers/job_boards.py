"""
Job Boards Scraper - Hiring trends from multiple job boards
Sources: LinkedIn (public), Indeed (public), Greenhouse/Lever APIs
No API key required for basic scraping
"""

import requests
import re
from datetime import datetime
import logging
from collections import Counter

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _scrape_greenhouse(company_slug: str) -> list[dict]:
    """Fetch jobs from Greenhouse API (used by many startups)."""
    jobs = []
    try:
        resp = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            for job in resp.json().get("jobs", [])[:50]:
                dept = job.get("departments", [{}])[0].get("name", "") if job.get("departments") else ""
                location = job.get("location", {}).get("name", "")
                jobs.append(
                    {
                        "title": job.get("title", ""),
                        "department": dept,
                        "location": location,
                        "url": job.get("absolute_url", ""),
                        "posted_at": job.get("updated_at", ""),
                        "source": "Greenhouse",
                    }
                )
    except Exception as e:
        logger.debug(f"Greenhouse scrape failed for {company_slug}: {e}")
    return jobs


def _scrape_lever(company_slug: str) -> list[dict]:
    """Fetch jobs from Lever API."""
    jobs = []
    try:
        resp = requests.get(
            f"https://api.lever.co/v0/postings/{company_slug}?mode=json",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            for job in resp.json()[:50]:
                jobs.append(
                    {
                        "title": job.get("text", ""),
                        "department": job.get("categories", {}).get("department", ""),
                        "location": job.get("categories", {}).get("location", ""),
                        "url": job.get("hostedUrl", ""),
                        "posted_at": str(datetime.fromtimestamp(job.get("createdAt", 0) / 1000).date()),
                        "source": "Lever",
                    }
                )
    except Exception as e:
        logger.debug(f"Lever scrape failed for {company_slug}: {e}")
    return jobs


def _slugify(company_name: str) -> str:
    """Convert company name to likely URL slug."""
    return re.sub(r"[^a-z0-9-]", "", company_name.lower().replace(" ", "-"))


def analyze_hiring_trends(jobs: list[dict]) -> dict:
    """Analyze job postings for hiring trends."""
    if not jobs:
        return {}

    # Count departments
    dept_counter = Counter(j.get("department", "Unknown") for j in jobs if j.get("department"))

    # Identify engineering vs non-engineering
    eng_keywords = ["engineer", "developer", "sre", "devops", "data", "ml", "ai", "science", "architect"]
    sales_keywords = ["sales", "account", "revenue", "business development", "bd"]
    marketing_keywords = ["marketing", "growth", "content", "seo", "brand"]
    product_keywords = ["product", "ux", "design", "researcher"]

    eng_count = sales_count = marketing_count = product_count = 0
    for j in jobs:
        title = j.get("title", "").lower()
        if any(k in title for k in eng_keywords):
            eng_count += 1
        if any(k in title for k in sales_keywords):
            sales_count += 1
        if any(k in title for k in marketing_keywords):
            marketing_count += 1
        if any(k in title for k in product_keywords):
            product_count += 1

    # Location analysis
    location_counter = Counter(
        j.get("location", "Unknown") for j in jobs if j.get("location")
    )
    remote_count = sum(
        1 for j in jobs if "remote" in (j.get("location") or "").lower()
    )

    # Infer growth phase
    if eng_count > (sales_count + marketing_count):
        growth_phase = "Product-building / R&D focused"
    elif sales_count > eng_count:
        growth_phase = "Sales-led growth / GTM expansion"
    else:
        growth_phase = "Balanced growth across functions"

    return {
        "total_open_roles": len(jobs),
        "engineering_roles": eng_count,
        "sales_roles": sales_count,
        "marketing_roles": marketing_count,
        "product_roles": product_count,
        "remote_roles": remote_count,
        "top_departments": dept_counter.most_common(5),
        "top_locations": location_counter.most_common(5),
        "inferred_growth_phase": growth_phase,
    }


def get_job_board_data(company_name: str) -> dict:
    """
    Fetch job postings from Greenhouse and Lever.
    Falls back gracefully if company not found.
    """
    result = {
        "source": "Job Boards (Greenhouse + Lever)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "all_jobs": [],
        "hiring_analysis": {},
        "boards_found": [],
        "error": None,
    }

    slug = _slugify(company_name)
    all_jobs = []

    gh_jobs = _scrape_greenhouse(slug)
    if gh_jobs:
        all_jobs.extend(gh_jobs)
        result["boards_found"].append("Greenhouse")

    lv_jobs = _scrape_lever(slug)
    if lv_jobs:
        all_jobs.extend(lv_jobs)
        result["boards_found"].append("Lever")

    # Try common slug variations
    if not all_jobs:
        # Remove common suffixes
        for suffix in ["-inc", "-corp", "-ai", "-hq"]:
            slug2 = slug.replace(suffix, "")
            if slug2 != slug:
                gh2 = _scrape_greenhouse(slug2)
                lv2 = _scrape_lever(slug2)
                if gh2:
                    all_jobs.extend(gh2)
                    result["boards_found"].append(f"Greenhouse ({slug2})")
                if lv2:
                    all_jobs.extend(lv2)
                    result["boards_found"].append(f"Lever ({slug2})")
                if all_jobs:
                    break

    result["all_jobs"] = all_jobs[:100]  # Cap at 100
    result["hiring_analysis"] = analyze_hiring_trends(all_jobs)

    if not all_jobs:
        result["error"] = "No job postings found on Greenhouse or Lever. Company may use a different ATS (Workday, iCIMS, etc.)."

    return result
