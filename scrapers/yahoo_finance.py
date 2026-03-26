"""
Financial Data Scraper — Global Coverage
Sources (in priority order):
  1. NSE India public API  — for Indian listed companies (free, no key, official)
  2. Finnhub API           — for US/global companies (free key, 60 calls/min)
  3. yfinance              — last resort fallback

IMPORTANT: All keys read from os.environ only (set by app.py at startup).
Never call st.secrets inside a thread — it fails silently.
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

# ── Known private companies ──────────────────────────────────────────
PRIVATE_COMPANIES = {
    "openai", "anthropic", "stripe", "notion", "figma", "canva",
    "databricks", "spacex", "klarna", "revolut", "chime", "brex",
    "plaid", "airtable", "miro", "linear", "vercel", "supabase",
    "retool", "posthog", "resend", "groq", "mistral", "perplexity",
    "swiggy", "zepto", "meesho", "razorpay", "cred", "dream11",
    "byju", "byjus", "unacademy", "vedantu", "physicswallah",
    "physics wallah", "lenskart", "pharmeasy",
}

# ── NSE symbol overrides (company name → NSE symbol) ─────────────────
NSE_SYMBOLS = {
    "tcs": "TCS", "tata consultancy": "TCS", "tata consultancy services": "TCS",
    "infosys": "INFY", "wipro": "WIPRO",
    "hcl": "HCLTECH", "hcl technologies": "HCLTECH", "hcltech": "HCLTECH",
    "tech mahindra": "TECHM", "techmahindra": "TECHM",
    "mphasis": "MPHASIS",
    "ltimindtree": "LTIM", "lti mindtree": "LTIM", "mindtree": "LTIM",
    "persistent": "PERSISTENT", "persistent systems": "PERSISTENT",
    "coforge": "COFORGE", "hexaware": "HEXAWARE",
    "cyient": "CYIENT", "zensar": "ZENSARTECH",
    "kpit": "KPITTECH", "birlasoft": "BSOFT", "mastek": "MASTEK",
    "reliance": "RELIANCE", "reliance industries": "RELIANCE",
    "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "bajaj finance": "BAJFINANCE", "bajaj": "BAJFINANCE",
    "asian paints": "ASIANPAINT",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "dr reddy": "DRREDDY", "dr. reddy": "DRREDDY", "dr reddys": "DRREDDY",
    "cipla": "CIPLA",
    "nykaa": "NYKAA",
    "paytm": "PAYTM", "one97": "PAYTM",
    "zomato": "ZOMATO",
    "delhivery": "DELHIVERY",
    "policybazaar": "POLICYBZR",
    "ola electric": "OLAELEC",
    "datamatics": "DATAMATICS",
    "infosystems": "DATAMATICS",  # Datamatics Global Services
    "wipro": "WIPRO",
    "ltts": "LTTS", "l&t technology": "LTTS", "lt technology": "LTTS",
    "l&t infotech": "LTI",
    "muthoot": "MUTHOOTFIN", "muthoot finance": "MUTHOOTFIN",
    "avenue supermarts": "DMART", "dmart": "DMART",
    "titan": "TITAN",
    "ultratech cement": "ULTRACEMCO", "ultratech": "ULTRACEMCO",
    "hindalco": "HINDALCO",
    "jsw steel": "JSWSTEEL",
    "coal india": "COALINDIA",
    "ntpc": "NTPC",
    "ongc": "ONGC",
    "bhel": "BHEL",
    "bpcl": "BPCL",
    "ioc": "IOC", "indian oil": "IOC",
    "power grid": "POWERGRID",
    "indusind bank": "INDUSINDBK",
    "axis bank": "AXISBANK",
    "kotak": "KOTAKBANK", "kotak mahindra": "KOTAKBANK",
    "hul": "HINDUNILVR", "hindustan unilever": "HINDUNILVR",
    "itc": "ITC",
    "nestle india": "NESTLEIND", "nestle": "NESTLEIND",
    "dabur": "DABUR",
    "godrej": "GODREJCP", "godrej consumer": "GODREJCP",
    "britannia": "BRITANNIA",
    "emami": "EMAMILTD",
    "havells": "HAVELLS",
    "voltas": "VOLTAS",
    "blue star": "BLUESTARCO",
    "polycab": "POLYCAB",
    "dixon": "DIXON",
    "amber enterprises": "AMBER",
    "indigo": "INDIGO", "interglobe": "INDIGO",
    "spicejet": "SPICEJET",
    "irctc": "IRCTC",
    "adani ports": "ADANIPORTS",
    "adani enterprises": "ADANIENT",
    "adani green": "ADANIGREEN",
    "adani total gas": "ATGL",
    "adani power": "ADANIPOWER",
    "adani wilmar": "AWL",
    "trent": "TRENT",
    "westlife": "WESTLIFE",
    "devyani": "DEVYANI",
    "sapphire foods": "SAPPHIRE",
    "jubilant foodworks": "JUBLFOOD",
}

# ── US / Global ticker overrides ─────────────────────────────────────
US_TICKERS = {
    "google": "GOOGL", "alphabet": "GOOGL", "microsoft": "MSFT",
    "apple": "AAPL", "amazon": "AMZN", "meta": "META",
    "netflix": "NFLX", "tesla": "TSLA", "nvidia": "NVDA",
    "shopify": "SHOP", "salesforce": "CRM", "atlassian": "TEAM",
    "cloudflare": "NET", "twilio": "TWLO", "datadog": "DDOG",
    "snowflake": "SNOW", "palantir": "PLTR", "hubspot": "HUBS",
    "adobe": "ADBE", "oracle": "ORCL", "servicenow": "NOW",
    "workday": "WDAY", "zoom": "ZM", "uber": "UBER",
    "airbnb": "ABNB", "coinbase": "COIN", "arm": "ARM",
    "astrazeneca": "AZN", "asml": "ASML", "sap": "SAP",
    "tsmc": "TSM", "taiwan semiconductor": "TSM",
    "sony": "SONY", "toyota": "TM", "honda": "HMC",
    "alibaba": "BABA", "tencent": "TCEHY", "baidu": "BIDU",
}


# ════════════════════════════════════════════════════════════════════
# NSE INDIA PUBLIC API  (no key required)
# ════════════════════════════════════════════════════════════════════

def _nse_session() -> requests.Session:
    """Create a session with NSE cookies (required to avoid 401)."""
    s = requests.Session()
    try:
        s.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=8)
    except Exception:
        pass
    return s


def _get_nse_quote(symbol: str) -> dict:
    """Fetch live quote from NSE India public API."""
    try:
        s = _nse_session()
        resp = s.get(
            f"https://www.nseindia.com/api/quote-equity?symbol={symbol}",
            headers=NSE_HEADERS,
            timeout=12,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"NSE quote error for {symbol}: {e}")
    return {}


def _get_nse_company_info(symbol: str) -> dict:
    """Fetch company info from NSE India API."""
    try:
        s = _nse_session()
        resp = s.get(
            f"https://www.nseindia.com/api/company-info?symbol={symbol}",
            headers=NSE_HEADERS,
            timeout=12,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"NSE company info error for {symbol}: {e}")
    return {}


def _fetch_via_nse(symbol: str) -> dict:
    """Fetch comprehensive data from NSE India for a given stock symbol."""
    result = {}
    symbol = symbol.upper().strip()

    quote_data = _get_nse_quote(symbol)
    if not quote_data:
        return result

    # Price data from priceInfo
    pi = quote_data.get("priceInfo", {})
    md = quote_data.get("metadata", {})
    si = quote_data.get("securityInfo", {})

    last_price = pi.get("lastPrice") or pi.get("close")
    if last_price:
        result["current_price"]      = round(float(last_price), 2)
        result["currency"]           = "INR"
        result["52w_high"]           = pi.get("weekHighLow", {}).get("max")
        result["52w_low"]            = pi.get("weekHighLow", {}).get("min")
        result["previous_close"]     = pi.get("previousClose")
        result["pe_ratio"]           = si.get("pe") or quote_data.get("priceInfo", {}).get("priceBand", {})

        prev = pi.get("previousClose")
        if prev and float(prev) > 0:
            chg = ((float(last_price) - float(prev)) / float(prev)) * 100
            result["price_change_30d_pct"] = round(chg, 2)
            today = datetime.utcnow().date()
            yesterday = (datetime.utcnow() - timedelta(days=1)).date()
            result["price_history_30d"] = [
                {"date": str(yesterday), "close": round(float(prev), 2)},
                {"date": str(today),     "close": round(float(last_price), 2)},
            ]

    # Company metadata
    if md:
        result["company_name"]   = md.get("companyName") or md.get("symbolName")
        result["sector"]         = md.get("industry")
        result["series"]         = md.get("series")
        mc = md.get("pdSectorPe") or md.get("marketCap")
        if mc:
            try:
                result["market_cap"] = float(mc) * 1_000_000  # NSE gives in millions INR
            except Exception:
                pass

    # Try company-info endpoint for more details
    ci = _get_nse_company_info(symbol)
    if ci:
        overview = ci.get("companyData", {})
        if overview:
            result["employee_count"] = overview.get("noOfEmployees")
            result["description"]    = (overview.get("businessDescription") or "")[:500]
            result["weburl"]         = overview.get("website")

    result["country"] = "India"
    result["exchange"] = "NSE"
    return result


# ════════════════════════════════════════════════════════════════════
# FINNHUB (US / global stocks)
# ════════════════════════════════════════════════════════════════════

def _finnhub_key() -> str:
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
            data = resp.json()
            return data if data else None
        logger.warning(f"Finnhub {endpoint} → {resp.status_code}")
    except Exception as e:
        logger.warning(f"Finnhub {endpoint} error: {e}")
    return None


def _fetch_via_finnhub(ticker: str) -> dict:
    result = {}

    quote = _finnhub_get("quote", {"symbol": ticker})
    if quote and quote.get("c"):
        curr = float(quote["c"])
        prev = float(quote.get("pc", 0))
        result["current_price"]  = round(curr, 2)
        result["previous_close"] = round(prev, 2)
        result["52w_high"]       = quote.get("h")
        result["52w_low"]        = quote.get("l")
        if prev > 0:
            result["price_change_30d_pct"] = round(((curr - prev) / prev) * 100, 2)
            today = datetime.utcnow().date()
            yesterday = (datetime.utcnow() - timedelta(days=1)).date()
            result["price_history_30d"] = [
                {"date": str(yesterday), "close": round(prev, 2)},
                {"date": str(today),     "close": round(curr, 2)},
            ]

    profile = _finnhub_get("stock/profile2", {"symbol": ticker})
    if profile and profile.get("name"):
        mc = profile.get("marketCapitalization", 0) or 0
        result["company_name"]   = profile.get("name")
        result["market_cap"]     = mc * 1_000_000
        result["employee_count"] = profile.get("employeeTotal")
        result["sector"]         = profile.get("finnhubIndustry")
        result["country"]        = profile.get("country")
        result["currency"]       = profile.get("currency", "USD")
        result["weburl"]         = profile.get("weburl")

    metrics = _finnhub_get("stock/metric", {"symbol": ticker, "metric": "all"})
    if metrics and metrics.get("metric"):
        m = metrics["metric"]
        result["pe_ratio"]      = m.get("peNormalizedAnnual")
        result["profit_margin"] = m.get("netProfitMarginAnnual")
        result["revenue_ttm"]   = m.get("revenueTTM")

    return result


# ════════════════════════════════════════════════════════════════════
# YFINANCE FALLBACK
# ════════════════════════════════════════════════════════════════════

def _fetch_via_yfinance(ticker: str) -> dict:
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
        result["weburl"]         = info.get("website")
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
        logger.warning(f"yfinance failed for {ticker}: {e}")
    return result


# ════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def get_financial_data(company_name: str) -> dict:
    """
    Fetch financial data for any global company.
    Priority: NSE India → Finnhub (US/global) → yfinance fallback
    """
    result = {
        "source": None,
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
        "description": None,
        "error": None,
    }

    name_lower = company_name.lower().strip()

    # 1. Known private company
    if name_lower in PRIVATE_COMPANIES:
        result["is_private"] = True
        result["source"]     = "N/A (private company)"
        result["error"]      = (
            f"{company_name} is a private company — no public stock data. "
            "Funding info sourced from Wikipedia/Wikidata instead."
        )
        return result

    # 2. Check if it's an Indian company → try NSE first
    nse_symbol = NSE_SYMBOLS.get(name_lower)

    # Also try partial match
    if not nse_symbol:
        for k, v in NSE_SYMBOLS.items():
            if k in name_lower or name_lower in k:
                nse_symbol = v
                break

    if nse_symbol:
        data = _fetch_via_nse(nse_symbol)
        if data and data.get("current_price"):
            result.update(data)
            result["ticker"] = nse_symbol
            result["source"] = f"NSE India ({nse_symbol})"
            return result
        # NSE API didn't return price — fall through to yfinance with .NS
        yf_ticker = nse_symbol + ".NS"
        data = _fetch_via_yfinance(yf_ticker)
        if data and data.get("current_price"):
            result.update(data)
            result["ticker"] = yf_ticker
            result["source"] = f"yfinance NSE ({yf_ticker})"
            return result

    # 3. US / global company → try Finnhub
    us_ticker = US_TICKERS.get(name_lower)
    if not us_ticker:
        # Search Finnhub
        search = _finnhub_get("search", {"q": company_name})
        if search and search.get("result"):
            for item in search["result"][:5]:
                if item.get("type") in ("Common Stock", "EQS"):
                    us_ticker = item["symbol"]
                    break
            if not us_ticker:
                us_ticker = search["result"][0].get("symbol")

    if us_ticker:
        data = _fetch_via_finnhub(us_ticker)
        if data and data.get("current_price"):
            result.update(data)
            result["ticker"] = us_ticker
            result["source"] = f"Finnhub ({us_ticker})"
            return result
        # Finnhub found ticker but no price — try yfinance
        data = _fetch_via_yfinance(us_ticker)
        if data and data.get("current_price"):
            result.update(data)
            result["ticker"] = us_ticker
            result["source"] = f"yfinance ({us_ticker})"
            return result

    # 4. Last resort — try yfinance directly with company name
    for suffix in ["", ".NS", ".BO"]:
        candidate = company_name.upper().replace(" ", "") + suffix
        data = _fetch_via_yfinance(candidate)
        if data and data.get("current_price"):
            result.update(data)
            result["ticker"] = candidate
            result["source"] = f"yfinance ({candidate})"
            return result

    result["source"] = "N/A"
    result["error"]  = (
        f"Could not find stock data for '{company_name}'. "
        "It may be unlisted, private, or too small to appear in our data sources. "
        "Financial context will be sourced from Wikipedia/Wikidata instead."
    )
    return result


def format_market_cap(value: float | int | None) -> str:
    if not value:
        return "N/A"
    # Show INR in Cr/Lakh format if currency is INR
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"
