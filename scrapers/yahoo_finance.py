"""
Financial Data Scraper — Global Coverage
Primary:  Finnhub API (free tier, 60 calls/min, official API)
Fallback: yfinance

Supports: US (NYSE/NASDAQ), India (NSE/BSE), UK (LSE), EU, SG, AU, etc.

IMPORTANT: FINNHUB_API_KEY must be set in os.environ BEFORE this module
is imported in a thread. app.py sets it at startup from st.secrets.
Never call st.secrets inside a thread — it fails silently.
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

# ── Known private companies (skip stock lookup immediately) ──────────
PRIVATE_COMPANIES = {
    # Global
    "openai", "anthropic", "stripe", "notion", "figma", "canva",
    "databricks", "spacex", "klarna", "revolut", "chime", "brex",
    "plaid", "airtable", "miro", "linear", "vercel", "supabase",
    "retool", "posthog", "resend", "groq", "mistral", "perplexity",
    # Indian private
    "swiggy", "zepto", "meesho", "slice", "kreditbee", "groww",
    "razorpay", "cred", "dream11", "byju", "byjus", "unacademy",
    "vedantu", "physicswallah", "physics wallah", "lenskart", "boat",
    "mamaearth", "nykaa fashion", "pharmeasy", "1mg", "healthkart",
}

# ── Ticker overrides: company name → exchange ticker ─────────────────
TICKER_OVERRIDES = {
    # US
    "google": "GOOGL", "alphabet": "GOOGL", "microsoft": "MSFT",
    "apple": "AAPL", "amazon": "AMZN", "meta": "META",
    "netflix": "NFLX", "tesla": "TSLA", "nvidia": "NVDA",
    "shopify": "SHOP", "salesforce": "CRM", "atlassian": "TEAM",
    "cloudflare": "NET", "twilio": "TWLO", "datadog": "DDOG",
    "snowflake": "SNOW", "palantir": "PLTR", "hubspot": "HUBS",
    "adobe": "ADBE", "oracle": "ORCL", "servicenow": "NOW",
    "workday": "WDAY", "zoom": "ZM", "uber": "UBER",
    "airbnb": "ABNB", "coinbase": "COIN", "robinhood": "HOOD",
    # Indian (NSE tickers — Finnhub uses NSE: prefix)
    "tcs": "NSE:TCS", "tata consultancy": "NSE:TCS",
    "tata consultancy services": "NSE:TCS",
    "infosys": "NSE:INFY", "wipro": "NSE:WIPRO",
    "hcl": "NSE:HCLTECH", "hcl technologies": "NSE:HCLTECH",
    "tech mahindra": "NSE:TECHM", "mphasis": "NSE:MPHASIS",
    "ltimindtree": "NSE:LTIM", "lti mindtree": "NSE:LTIM",
    "persistent systems": "NSE:PERSISTENT",
    "reliance": "NSE:RELIANCE", "reliance industries": "NSE:RELIANCE",
    "hdfc bank": "NSE:HDFCBANK", "hdfc": "NSE:HDFCBANK",
    "icici bank": "NSE:ICICIBANK", "icici": "NSE:ICICIBANK",
    "sbi": "NSE:SBIN", "state bank": "NSE:SBIN",
    "bajaj finance": "NSE:BAJFINANCE", "bajaj": "NSE:BAJFINANCE",
    "asian paints": "NSE:ASIANPAINT",
    "maruti": "NSE:MARUTI", "maruti suzuki": "NSE:MARUTI",
    "tata motors": "NSE:TATAMOTORS",
    "tata steel": "NSE:TATASTEEL",
    "sun pharma": "NSE:SUNPHARMA", "sun pharmaceutical": "NSE:SUNPHARMA",
    "dr reddy": "NSE:DRREDDY", "dr. reddy": "NSE:DRREDDY",
    "cipla": "NSE:CIPLA",
    "nykaa": "NSE:NYKAA",
    "paytm": "NSE:PAYTM", "one97": "NSE:PAYTM",
    "zomato": "NSE:ZOMATO",
    "delhivery": "NSE:DELHIVERY",
    "policybazaar": "NSE:POLICYBZR",
    "ola": "NSE:OLAELEC",  # Ola Electric (listed)
    "datamatics": "NSE:DATAMATICS",
    "wipro": "NSE:WIPRO",
    "mindtree": "NSE:LTIM",
    "hexaware": "NSE:HEXAWARE",
    "cyient": "NSE:CYIENT",
    "zensar": "NSE:ZENSARTECH",
    "kpit": "NSE:KPITTECH",
    "coforge": "NSE:COFORGE",
    "birlasoft": "NSE:BSOFT",
    "mastek": "NSE:MASTEK",
    # UK
    "arm": "ARM", "arm holdings": "ARM",
    "unilever": "UL", "bp": "BP", "shell": "SHEL",
    "astrazeneca": "AZN", "glaxo": "GSK", "gsk": "GSK",
    "hsbc": "HSBC", "barclays": "BCS",
    # EU
    "sap": "SAP", "asml": "ASML", "lvmh": "LVMHF",
    "volkswagen": "VWAGY", "bmw": "BMWYY",
    "siemens": "SIEGY", "allianz": "ALIZY",
    # Asia / Other
    "samsung": "005930.KS", "lg": "066570.KS",
    "tsmc": "TSM", "taiwan semiconductor": "TSM",
    "sony": "SONY", "toyota": "TM", "honda": "HMC",
    "alibaba": "BABA", "tencent": "TCEHY", "baidu": "BIDU",
    "sea limited": "SE", "grab": "GRAB", "shopee": "SE",
}

# ── Country → exchange suffix hints for yfinance fallback ────────────
INDIA_KEYWORDS = {
    "nse", "bse", "india", "indian", "ltd", "limited",
    "technologies", "infotech", "infosystems",
}


def _finnhub_key() -> str:
    """Read from env only — never call st.secrets inside a thread."""
    return os.getenv("FINNHUB_API_KEY", "")


def _finnhub_get(endpoint: str, params: dict) -> dict | None:
    key = _finnhub_key()
    if not key:
        return None
    try:
        resp = requests.get(
            f"{FINNHUB_BASE}/{endpoint}",
            params={**params, "token": key},
            timeout=12,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Finnhub {endpoint} returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Finnhub error on {endpoint}: {e}")
    return None


def _guess_ticker(company_name: str) -> str | None:
    """
    Resolve company name to a ticker.
    1. Check override table (covers Indian NSE tickers too)
    2. Search Finnhub
    3. Try NSE suffix heuristic for Indian companies
    """
    key = company_name.lower().strip()

    # Direct override
    if key in TICKER_OVERRIDES:
        return TICKER_OVERRIDES[key]

    # Partial match in overrides (e.g. "Datamatics Global" → "datamatics")
    for override_key, ticker in TICKER_OVERRIDES.items():
        if override_key in key or key in override_key:
            return ticker

    # Finnhub search
    data = _finnhub_get("search", {"q": company_name})
    if data and data.get("result"):
        for item in data["result"][:8]:
            sym  = item.get("symbol", "")
            typ  = item.get("type", "")
            desc = item.get("description", "").lower()
            # Prefer exact or close name matches
            if typ in ("Common Stock", "EQS") and (
                company_name.lower() in desc or desc in company_name.lower()
            ):
                return sym
        # Fall back to first result
        return data["result"][0].get("symbol")

    # Heuristic: Indian company names often end in common suffixes
    # Try appending .NS (NSE via yfinance convention)
    clean = company_name.upper().replace(" ", "").replace(".", "").replace(",", "")
    for suffix in [".NS", ".BO"]:
        candidate = clean + suffix
        try:
            import yfinance as yf
            t = yf.Ticker(candidate)
            info = t.fast_info
            if hasattr(info, "last_price") and info.last_price:
                return candidate
        except Exception:
            pass

    return None


def _get_via_finnhub(ticker: str) -> dict:
    """Fetch quote + profile + metrics from Finnhub free tier."""
    result = {}

    # Real-time quote
    quote = _finnhub_get("quote", {"symbol": ticker})
    if quote and quote.get("c"):
        result["current_price"]  = round(float(quote["c"]), 2)
        result["previous_close"] = round(float(quote.get("pc", 0)), 2)
        result["52w_high"]       = quote.get("h")
        result["52w_low"]        = quote.get("l")
        if result["previous_close"] and result["previous_close"] > 0:
            chg = ((result["current_price"] - result["previous_close"])
                   / result["previous_close"]) * 100
            result["price_change_30d_pct"] = round(chg, 2)
            today     = datetime.utcnow().date()
            yesterday = (datetime.utcnow() - timedelta(days=1)).date()
            result["price_history_30d"] = [
                {"date": str(yesterday), "close": result["previous_close"]},
                {"date": str(today),     "close": result["current_price"]},
            ]

    # Company profile
    profile = _finnhub_get("stock/profile2", {"symbol": ticker})
    if profile and profile.get("name"):
        mc_millions = profile.get("marketCapitalization", 0) or 0
        result["company_name"]   = profile.get("name")
        result["market_cap"]     = mc_millions * 1_000_000
        result["employee_count"] = profile.get("employeeTotal")
        result["sector"]         = profile.get("finnhubIndustry")
        result["country"]        = profile.get("country")
        result["currency"]       = profile.get("currency", "USD")
        result["ipo_date"]       = profile.get("ipo")
        result["weburl"]         = profile.get("weburl")
        result["logo"]           = profile.get("logo")

    # Basic metrics (P/E, margins etc.)
    metrics = _finnhub_get("stock/metric", {"symbol": ticker, "metric": "all"})
    if metrics and metrics.get("metric"):
        m = metrics["metric"]
        result["pe_ratio"]      = m.get("peNormalizedAnnual")
        result["profit_margin"] = m.get("netProfitMarginAnnual")
        result["eps"]           = m.get("epsNormalizedAnnual")
        result["revenue_ttm"]   = m.get("revenueTTM")
        if m.get("52WeekHigh"):
            result["52w_high"] = m["52WeekHigh"]
        if m.get("52WeekLow"):
            result["52w_low"]  = m["52WeekLow"]

    return result


def _get_via_yfinance(ticker: str) -> dict:
    """Fallback to yfinance. Works for NSE (.NS) and BSE (.BO) tickers too."""
    result = {}
    try:
        import yfinance as yf
        t    = yf.Ticker(ticker)
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
        result["country"]        = info.get("country")
        result["description"]    = (info.get("longBusinessSummary") or "")[:500]
        result["weburl"]         = info.get("website")

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
        logger.warning(f"yfinance failed for {ticker}: {e}")
    return result


def get_financial_data(company_name: str) -> dict:
    """
    Fetch financial data for any global company.
    Supports US, India (NSE/BSE), UK, EU, Asia.
    """
    result = {
        "source": "Finnhub API",
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
        "country": None,
        "is_private": False,
        "weburl": None,
        "error": None,
    }

    name_lower = company_name.lower().strip()

    # Known private company — skip immediately
    if name_lower in PRIVATE_COMPANIES:
        result["is_private"] = True
        result["source"]     = "N/A (private company)"
        result["error"]      = (
            f"{company_name} is a private company — no public stock data available. "
            "Funding info sourced from Wikipedia/Wikidata instead."
        )
        return result

    # Resolve ticker
    ticker = _guess_ticker(company_name)
    if not ticker:
        result["error"] = (
            f"Could not resolve ticker for '{company_name}'. "
            "It may be private, very small, or try the exact stock ticker symbol."
        )
        return result

    result["ticker"] = ticker
    has_finnhub_key  = bool(_finnhub_key())

    # ── Try Finnhub first ────────────────────────────────────────────
    if has_finnhub_key:
        # For Indian NSE tickers (NSE:XXX format), strip prefix for Finnhub
        finnhub_ticker = ticker.replace("NSE:", "").replace("BSE:", "")
        data = _get_via_finnhub(finnhub_ticker)
        if data and data.get("current_price"):
            result.update(data)
            result["source"] = f"Finnhub API ({ticker})"
            return result
        # Finnhub may not cover Indian stocks well — try yfinance next
        logger.info(f"Finnhub returned no price for {ticker}, trying yfinance")

    # ── Fallback: yfinance (supports .NS / .BO suffixes natively) ────
    result["source"] = f"yfinance ({ticker})"
    # Convert NSE: format to yfinance .NS format
    yf_ticker = ticker
    if ticker.startswith("NSE:"):
        yf_ticker = ticker.replace("NSE:", "") + ".NS"
    elif ticker.startswith("BSE:"):
        yf_ticker = ticker.replace("BSE:", "") + ".BO"

    data = _get_via_yfinance(yf_ticker)
    if data and data.get("current_price"):
        result.update(data)
        result["ticker"] = yf_ticker
        return result

    # Both failed
    result["error"] = (
        f"Could not fetch financial data for '{company_name}' (ticker: {ticker}). "
        + ("Finnhub key found but returned no data — company may not be covered. " if has_finnhub_key else "No FINNHUB_API_KEY set. ")
        + "yfinance also failed (rate-limited on shared IPs). "
        "Try adding the company's exact NSE/BSE ticker to TICKER_OVERRIDES."
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
