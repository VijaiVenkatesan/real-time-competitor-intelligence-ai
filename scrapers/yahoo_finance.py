"""
Financial Data Scraper
Primary:  Finnhub API  — free tier, 60 calls/min, no IP blocking, official API
Fallback: yfinance     — works sometimes on local/non-shared IPs

Finnhub free tier: https://finnhub.io/register  (free, no credit card)
Add FINNHUB_API_KEY to Streamlit secrets for best results.
Without a key, falls back to yfinance.
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

# Known private companies — skip all stock lookups immediately
PRIVATE_COMPANIES = {
    "openai", "anthropic", "stripe", "notion", "figma", "canva",
    "databricks", "spacex", "klarna", "revolut", "chime", "brex",
    "plaid", "airtable", "miro", "linear", "vercel", "supabase",
    "retool", "posthog", "cal.com", "resend",
}

# Ticker overrides for well-known public companies
TICKER_OVERRIDES = {
    "google": "GOOGL", "alphabet": "GOOGL", "microsoft": "MSFT",
    "apple": "AAPL", "amazon": "AMZN", "meta": "META",
    "netflix": "NFLX", "tesla": "TSLA", "nvidia": "NVDA",
    "shopify": "SHOP", "salesforce": "CRM", "atlassian": "TEAM",
    "cloudflare": "NET", "twilio": "TWLO", "datadog": "DDOG",
    "snowflake": "SNOW", "palantir": "PLTR", "hubspot": "HUBS",
    "adobe": "ADBE", "oracle": "ORCL", "sap": "SAP",
    "servicenow": "NOW", "workday": "WDAY", "zendesk": "ZEN",
    "zoom": "ZM", "slack": "WORK", "twitter": "TWTR",
}


def _get_finnhub_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("FINNHUB_API_KEY", os.getenv("FINNHUB_API_KEY", ""))
    except Exception:
        return os.getenv("FINNHUB_API_KEY", "")


def _finnhub_get(endpoint: str, params: dict) -> dict | None:
    """Make a Finnhub API call. Returns None on error."""
    key = _get_finnhub_key()
    if not key:
        return None
    try:
        resp = requests.get(
            f"{FINNHUB_BASE}/{endpoint}",
            params={**params, "token": key},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Finnhub {endpoint} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Finnhub error: {e}")
    return None


def _search_ticker_finnhub(company_name: str) -> str | None:
    """Search Finnhub for a company ticker."""
    data = _finnhub_get("search", {"q": company_name})
    if data and data.get("result"):
        # Prefer exact matches or common stock (type = "Common Stock")
        for item in data["result"][:5]:
            if item.get("type") in ("Common Stock", "EQS"):
                return item.get("symbol")
        return data["result"][0].get("symbol")
    return None


def _get_via_finnhub(ticker: str) -> dict:
    """Fetch stock quote and company profile from Finnhub."""
    result = {}

    # Quote (real-time price)
    quote = _finnhub_get("quote", {"symbol": ticker})
    if quote and quote.get("c"):
        result["current_price"]      = round(quote["c"], 2)
        result["price_change_pct"]   = round(quote.get("dp", 0), 2)
        result["52w_high"]           = quote.get("h")
        result["52w_low"]            = quote.get("l")
        result["previous_close"]     = quote.get("pc")

    # Company profile
    profile = _finnhub_get("stock/profile2", {"symbol": ticker})
    if profile:
        result["company_name"]   = profile.get("name")
        result["market_cap"]     = profile.get("marketCapitalization", 0) * 1e6  # Finnhub gives millions
        result["employee_count"] = profile.get("employeeTotal")
        result["sector"]         = profile.get("finnhubIndustry")
        result["country"]        = profile.get("country")
        result["currency"]       = profile.get("currency", "USD")
        result["ipo_date"]       = profile.get("ipo")
        result["logo"]           = profile.get("logo")
        result["weburl"]         = profile.get("weburl")

    # Basic financials (P/E, revenue etc.)
    metrics = _finnhub_get("stock/metric", {"symbol": ticker, "metric": "all"})
    if metrics and metrics.get("metric"):
        m = metrics["metric"]
        result["pe_ratio"]      = m.get("peNormalizedAnnual")
        result["revenue_ttm"]   = m.get("revenuePerShareAnnual")
        result["profit_margin"] = m.get("netProfitMarginAnnual")
        result["eps"]           = m.get("epsNormalizedAnnual")
        result["52w_high"]      = m.get("52WeekHigh") or result.get("52w_high")
        result["52w_low"]       = m.get("52WeekLow")  or result.get("52w_low")

    # NOTE: stock/candle requires Finnhub premium (403 on free tier).
    # Instead derive price change from current price vs previous close.
    # For a chart we build a synthetic 2-point history from quote data.
    if result.get("current_price") and result.get("previous_close"):
        curr = result["current_price"]
        prev = result["previous_close"]
        result["price_change_30d_pct"] = round(((curr - prev) / prev) * 100, 2)
        # Minimal history for chart display (today vs yesterday)
        today     = datetime.utcnow().date()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date()
        result["price_history_30d"] = [
            {"date": str(yesterday), "close": round(prev, 2)},
            {"date": str(today),     "close": round(curr, 2)},
        ]

    return result


def _get_via_yfinance(ticker: str) -> dict:
    """Fallback: try yfinance (may be rate-limited on shared IPs)."""
    result = {}
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        if not info or len(info) < 5:
            return result
        result["current_price"]  = info.get("currentPrice") or info.get("regularMarketPrice")
        result["market_cap"]     = info.get("marketCap")
        result["pe_ratio"]       = info.get("trailingPE")
        result["52w_high"]       = info.get("fiftyTwoWeekHigh")
        result["52w_low"]        = info.get("fiftyTwoWeekLow")
        result["revenue_ttm"]    = info.get("totalRevenue")
        result["profit_margin"]  = info.get("profitMargins")
        result["employee_count"] = info.get("fullTimeEmployees")
        result["sector"]         = info.get("sector")
        result["currency"]       = info.get("currency", "USD")
        result["description"]    = (info.get("longBusinessSummary") or "")[:500]
        hist = t.history(period="1mo")
        if not hist.empty:
            prices = hist["Close"].tolist()
            dates  = [str(d.date()) for d in hist.index]
            result["price_history_30d"] = [
                {"date": d, "close": round(p, 2)} for d, p in zip(dates, prices)
            ]
            if len(prices) >= 2:
                result["price_change_30d_pct"] = round(
                    ((prices[-1] - prices[0]) / prices[0]) * 100, 2
                )
    except Exception as e:
        logger.warning(f"yfinance fallback failed for {ticker}: {e}")
    return result


def get_financial_data(company_name: str) -> dict:
    """
    Fetch financial data. Uses Finnhub if API key available, falls back to yfinance.
    """
    result = {
        "source": "Finnhub (free API)",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "ticker": None,
        "current_price": None,
        "currency": "USD",
        "market_cap": None,
        "pe_ratio": None,
        "52w_high": None,
        "52w_low": None,
        "revenue_ttm": None,
        "profit_margin": None,
        "price_change_30d_pct": None,
        "price_history_30d": [],
        "employee_count": None,
        "sector": None,
        "is_private": False,
        "description": None,
        "error": None,
    }

    key = company_name.lower().strip()

    # Known private company — skip immediately
    if key in PRIVATE_COMPANIES:
        result["is_private"] = True
        result["source"] = "N/A (private company)"
        result["error"] = (
            f"{company_name} is a private company — no public stock data. "
            "Funding info sourced from Wikipedia/Wikidata."
        )
        return result

    # Resolve ticker
    ticker = TICKER_OVERRIDES.get(key)
    if not ticker:
        ticker = _search_ticker_finnhub(company_name)
    if not ticker:
        result["error"] = (
            "Could not resolve ticker. Company may be private, "
            "non-US listed, or try adding FINNHUB_API_KEY to secrets."
        )
        return result

    result["ticker"] = ticker

    # Try Finnhub first
    finnhub_key = _get_finnhub_key()
    if finnhub_key:
        data = _get_via_finnhub(ticker)
        if data:
            result.update(data)
            return result
        result["error"] = "Finnhub returned no data for this ticker."

    # Fallback to yfinance
    result["source"] = "yfinance (fallback)"
    data = _get_via_yfinance(ticker)
    if data:
        result.update(data)
        result.pop("error", None)
    else:
        result["error"] = (
            "Both Finnhub and yfinance failed. "
            "Add FINNHUB_API_KEY to Streamlit secrets for reliable stock data. "
            "Get a free key at finnhub.io/register (no credit card)."
        )

    return result


def format_market_cap(value: float | int | None) -> str:
    if not value:
        return "N/A"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"
