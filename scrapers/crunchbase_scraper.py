"""
Funding & Company Data Scraper — replaces Crunchbase
Sources:
  1. Wikipedia REST API  — free, no key, structured infobox data
  2. OpenCorporates API  — free tier, no key needed for basic company search
  3. Wikidata API        — free, machine-readable facts about companies

Crunchbase blocks scraping with JS rendering + bot detection, so we use
these reliable, truly free alternatives instead.
"""

import requests
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "CompetitorIntelligenceBot/1.0 (research tool)"}


# ── Wikipedia REST API ──────────────────────────────────────────────
def _get_wikipedia_summary(company_name: str) -> dict:
    """Fetch Wikipedia page summary — includes founding date, HQ, description."""
    data = {}
    try:
        slug = company_name.replace(" ", "_")
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            j = resp.json()
            data["description"] = j.get("extract", "")[:500]
            data["wikipedia_url"] = j.get("content_urls", {}).get("desktop", {}).get("page", "")
            data["thumbnail_url"] = (j.get("thumbnail") or {}).get("source", "")
    except Exception as e:
        logger.debug(f"Wikipedia summary error: {e}")
    return data


def _get_wikidata_facts(company_name: str) -> dict:
    """Query Wikidata SPARQL for company facts (founded, employees, revenue, HQ)."""
    data = {}
    try:
        sparql = f"""
        SELECT ?item ?founded ?employees ?revenue ?hq ?hqLabel WHERE {{
          ?item wikibase:sitelinks ?sitelinks.
          ?item rdfs:label "{company_name}"@en.
          OPTIONAL {{ ?item wdt:P571 ?founded. }}
          OPTIONAL {{ ?item wdt:P1128 ?employees. }}
          OPTIONAL {{ ?item wdt:P2139 ?revenue. }}
          OPTIONAL {{ ?item wdt:P159 ?hq. ?hq rdfs:label ?hqLabel. FILTER(LANG(?hqLabel)="en") }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }} LIMIT 1
        """
        resp = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=12,
        )
        if resp.status_code == 200:
            bindings = resp.json().get("results", {}).get("bindings", [])
            if bindings:
                b = bindings[0]
                if "founded" in b:
                    data["founded_year"] = b["founded"]["value"][:4]
                if "employees" in b:
                    data["employee_count"] = b["employees"]["value"]
                if "revenue" in b:
                    data["revenue_usd"] = b["revenue"]["value"]
                if "hqLabel" in b:
                    data["headquarters"] = b["hqLabel"]["value"]
    except Exception as e:
        logger.debug(f"Wikidata error: {e}")
    return data


def _get_opencorporates(company_name: str) -> dict:
    """Search OpenCorporates for company registration data (free, no key for basic search)."""
    data = {}
    try:
        resp = requests.get(
            "https://api.opencorporates.com/v0.4/companies/search",
            params={
                "q": company_name,
                "per_page": 1,
                "order": "score",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", {}).get("companies", [])
            if results:
                co = results[0].get("company", {})
                data["registered_name"]    = co.get("name")
                data["jurisdiction"]       = co.get("jurisdiction_code", "").upper()
                data["company_number"]     = co.get("company_number")
                data["incorporation_date"] = co.get("incorporation_date")
                data["company_type"]       = co.get("company_type")
                data["registered_address"] = (co.get("registered_address") or {}).get("in_full")
                data["opencorporates_url"] = co.get("opencorporates_url")
                data["inactive"]           = co.get("inactive", False)
    except Exception as e:
        logger.debug(f"OpenCorporates error: {e}")
    return data


def get_funding_data(company_name: str) -> dict:
    """
    Aggregate company data from Wikipedia + Wikidata + OpenCorporates.
    All sources are free with no API key required.
    """
    result = {
        "source": "Wikipedia + Wikidata + OpenCorporates (all free, no key)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        # Keep these keys for interface compatibility with original Crunchbase scraper
        "total_funding_usd": None,
        "total_funding_formatted": None,
        "funding_rounds": None,
        "last_funding_date": None,
        "last_funding_type": None,
        "investor_count": None,
        "employee_range": None,
        "founded_year": None,
        # New keys
        "headquarters": None,
        "description": None,
        "wikipedia_url": None,
        "registered_name": None,
        "incorporation_date": None,
        "jurisdiction": None,
        "company_type": None,
        "registered_address": None,
        "opencorporates_url": None,
        "error": None,
        "note": "Funding data from Wikipedia/Wikidata (private companies may have limited data). For detailed VC funding, check Crunchbase or PitchBook manually.",
    }

    wiki_data  = _get_wikipedia_summary(company_name)
    wikidata   = _get_wikidata_facts(company_name)
    opencorp   = _get_opencorporates(company_name)

    result.update(wiki_data)
    result.update(wikidata)
    result.update(opencorp)

    # Try to extract funding mentions from Wikipedia description
    desc = result.get("description", "") or ""
    funding_match = re.search(
        r"\$([0-9,.]+)\s*(billion|million|B|M)\b",
        desc,
        re.IGNORECASE,
    )
    if funding_match:
        amount_str = funding_match.group(1).replace(",", "")
        unit = funding_match.group(2).lower()
        try:
            amount = float(amount_str)
            if unit in ("billion", "b"):
                result["total_funding_usd"] = int(amount * 1e9)
                result["total_funding_formatted"] = f"${amount:.2f}B (approx, from Wikipedia)"
            elif unit in ("million", "m"):
                result["total_funding_usd"] = int(amount * 1e6)
                result["total_funding_formatted"] = f"${amount:.0f}M (approx, from Wikipedia)"
        except ValueError:
            pass

    if not any([wiki_data, wikidata, opencorp]):
        result["error"] = (
            "No data found. Company may be very new, private, or not well-documented on Wikipedia/Wikidata."
        )

    return result
