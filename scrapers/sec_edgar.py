"""
SEC Edgar Scraper - Official 10-K, 10-Q filings
Uses: SEC EDGAR full-text search API (free, no key needed)
"""

import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&dateRange=custom&startdt={start}&enddt={end}&forms={form}"
EDGAR_COMPANY_SEARCH = "https://www.sec.gov/cgi-bin/browse-edgar"
EDGAR_DATA = "https://data.sec.gov"

HEADERS = {
    "User-Agent": "CompetitorIntelligenceBot research@example.com",
    "Accept": "application/json",
}


def search_company_cik(company_name: str) -> str | None:
    """Find the SEC CIK number for a company."""
    try:
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": company_name, "dateRange": "custom", "startdt": "2020-01-01", "forms": "10-K"},
            headers=HEADERS,
            timeout=10,
        )
        # Try the company search API
        resp2 = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={
                "company": company_name,
                "CIK": "",
                "type": "10-K",
                "dateb": "",
                "owner": "include",
                "count": "5",
                "search_text": "",
                "action": "getcompany",
                "output": "atom",
            },
            headers=HEADERS,
            timeout=10,
        )
        # Parse atom feed for CIK
        import re
        match = re.search(r"CIK=(\d+)", resp2.text)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"SEC CIK search failed: {e}")
    return None


def get_sec_filings(company_name: str, max_filings: int = 5) -> dict:
    """
    Fetch recent SEC filings (10-K annual, 10-Q quarterly) for a company.
    """
    result = {
        "source": "SEC Edgar",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "cik": None,
        "recent_10k": [],
        "recent_10q": [],
        "key_metrics_from_filings": {},
        "error": None,
    }

    cik = search_company_cik(company_name)
    if not cik:
        # Fall back to EDGAR full-text search for recent filings mentioning the company
        result["error"] = "Could not resolve CIK - company may not be publicly traded or listed differently"
        result["note"] = "Only public US companies have SEC filings. Private companies will show N/A."
        return result

    result["cik"] = cik
    cik_padded = cik.zfill(10)

    try:
        # Get filing submissions
        resp = requests.get(
            f"{EDGAR_DATA}/submissions/CIK{cik_padded}.json",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            result["error"] = f"SEC data fetch returned status {resp.status_code}"
            return result

        data = resp.json()
        company_name_official = data.get("name", company_name)
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocument", [])

        for i, form in enumerate(forms):
            entry = {
                "form": form,
                "filing_date": dates[i] if i < len(dates) else "",
                "accession_number": accessions[i] if i < len(accessions) else "",
                "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accessions[i].replace('-','')}/{descriptions[i] if i < len(descriptions) else ''}" if i < len(accessions) else "",
            }
            if form == "10-K" and len(result["recent_10k"]) < max_filings:
                result["recent_10k"].append(entry)
            elif form == "10-Q" and len(result["recent_10q"]) < max_filings:
                result["recent_10q"].append(entry)

            if len(result["recent_10k"]) >= max_filings and len(result["recent_10q"]) >= max_filings:
                break

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"SEC Edgar error for {company_name}: {e}")

    return result
