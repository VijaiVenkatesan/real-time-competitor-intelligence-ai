"""
Yahoo Finance Scraper - Real-time stock price, market cap, financials
No API key required - uses yfinance library.
Includes retry logic and rate-limit handling.
"""

import time
import random
import logging
from datetime import datetime

import yfinance as yf

logger = logging.getLogger(__name__)

# Common ticker overrides for well-known private/non-US companies
# yfinance search sometimes returns wrong tickers for these
TICKER_OVERRIDES = {
    "openai":       None,   # private company — no ticker
    "anthropic":    None,
    "stripe":       None,
    "notion":       None,
    "figma":        None,
    "canva":        None,
    "databricks":   None,
    "spacex":       None,
    "shopify":      "SHOP",
    "microsoft":    "MSFT",
    "google":       "GOOGL",
    "alphabet":     "GOOGL",
    "amazon":       "AMZN",
    "apple":        "AAPL",
    "meta":         "META",
    "netflix":      "NFLX",
    "tesla":        "TSLA",
    "nvidia":       "NVDA",
    "salesforce":   "CRM",
    "atlassian":    "TEAM",
    "cloudflare":   "NET",
    "twilio":       "TWLO",
    "datadog":      "DDOG",
    "snowflake":    "SNOW",
    "palantir":     "PLTR",
    "hubspot":      "HUBS",
    "zendesk":      "ZEN",
}


def get_stock_ticker(company_name: str) -> str | None:
    """
    Resolve a company name to a ticker symbol.
    Checks override dict first, then queries Yahoo Finance search API.
    Returns None for known private companies.
    """
    key = company_name.lower().strip()

    # Check override table first
    if key in TICKER_OVERRIDES:
        ticker = TICKER_OVERRIDES[key]
        if ticker is None:
            logger.info(f"{company_name} is a known private company — no ticker")
        return ticker

    # Query Yahoo Finance search endpoint with retry
    import requests
    for attempt in range(3):
        try:
            resp = requests.get(
                "https://query2.finance.yahoo.com/v1/finance/search",
                params={"q": company_name, "quotesCount": 1, "newsCount": 0},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/122.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 429:
                wait = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"Yahoo rate limited, waiting {wait:.1f}s (attempt {attempt+1})")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                break
            quotes = resp.json().get("quotes", [])
            if quotes:
                return quotes[0].get("symbol")
        except Exception as e:
            logger.warning(f"Ticker lookup attempt {attempt+1} failed: {e}")
            time.sleep(1)

    return None


def get_financial_data(company_name: str) -> dict:
    """
    Fetch real-time financial data from Yahoo Finance.
    Returns stock price, market cap, P/E ratio, revenue, and 30-day price history.
    Handles rate limits with exponential backoff.
    """
    result = {
        "source": "Yahoo Finance",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "ticker": None,
        "current_price": None,
        "currency": None,
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
        "industry": None,
        "description": None,
        "is_private": False,
        "error": None,
    }

    ticker_symbol = get_stock_ticker(company_name)

    # Known private company
    if ticker_symbol is None and company_name.lower().strip() in TICKER_OVERRIDES:
        result["is_private"] = True
        result["error"] = (
            f"{company_name} is a private company — no public stock data available. "
            "Financial data sourced from Wikipedia/Wikidata instead."
        )
        return result

    if not ticker_symbol:
        result["error"] = (
            "Could not resolve ticker symbol. Company may be private, "
            "non-US listed, or named differently on exchanges."
        )
        return result

    result["ticker"] = ticker_symbol

    # Fetch with retry on rate limit
    for attempt in range(3):
        try:
            ticker = yf.Ticker(ticker_symbol)
            info   = ticker.info

            # yfinance returns an empty/minimal dict on rate limit — detect it
            if not info or len(info) < 5:
                if attempt < 2:
                    wait = 2 ** attempt + random.uniform(0.5, 1.5)
                    logger.warning(f"Empty yfinance response, retrying in {wait:.1f}s")
                    time.sleep(wait)
                    continue
                else:
                    result["error"] = "Yahoo Finance returned empty data (rate limited). Try again in 30s."
                    return result

            result["current_price"]      = info.get("currentPrice") or info.get("regularMarketPrice")
            result["currency"]           = info.get("currency", "USD")
            result["market_cap"]         = info.get("marketCap")
            result["pe_ratio"]           = info.get("trailingPE")
            result["52w_high"]           = info.get("fiftyTwoWeekHigh")
            result["52w_low"]            = info.get("fiftyTwoWeekLow")
            result["revenue_ttm"]        = info.get("totalRevenue")
            result["profit_margin"]      = info.get("profitMargins")
            result["employee_count"]     = info.get("fullTimeEmployees")
            result["sector"]             = info.get("sector")
            result["industry"]           = info.get("industry")
            result["description"]        = (info.get("longBusinessSummary") or "")[:500]

            # 30-day price history
            hist = ticker.history(period="1mo")
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

            break  # success — exit retry loop

        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "too many" in err_str or "rate" in err_str:
                if attempt < 2:
                    wait = 3 ** attempt + random.uniform(1, 2)
                    logger.warning(f"Yahoo Finance rate limited, waiting {wait:.1f}s")
                    time.sleep(wait)
                    continue
                result["error"] = (
                    "Yahoo Finance rate limited (Too Many Requests). "
                    "This is temporary — retry in 30–60 seconds."
                )
            else:
                result["error"] = str(e)
                logger.error(f"Yahoo Finance error for {company_name}: {e}")
            break

    return result


def format_market_cap(value: int | None) -> str:
    if not value:
        return "N/A"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,}"
