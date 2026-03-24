"""
Yahoo Finance Scraper - Real-time stock price, market cap, financials
No API key required - uses yfinance library
"""

import yfinance as yf
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def get_stock_ticker(company_name: str) -> str | None:
    """Attempt to resolve a company name to a ticker symbol."""
    try:
        import requests
        # Use Yahoo Finance search endpoint
        url = f"https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": company_name, "quotesCount": 1, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        quotes = data.get("quotes", [])
        if quotes:
            return quotes[0].get("symbol")
    except Exception as e:
        logger.warning(f"Ticker lookup failed: {e}")
    return None


def get_financial_data(company_name: str) -> dict:
    """
    Fetch real-time financial data from Yahoo Finance.
    Returns stock price, market cap, P/E ratio, revenue, and 30-day price history.
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
        "error": None,
    }

    ticker_symbol = get_stock_ticker(company_name)
    if not ticker_symbol:
        result["error"] = "Could not resolve ticker symbol"
        return result

    result["ticker"] = ticker_symbol

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        result["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["currency"] = info.get("currency", "USD")
        result["market_cap"] = info.get("marketCap")
        result["pe_ratio"] = info.get("trailingPE")
        result["52w_high"] = info.get("fiftyTwoWeekHigh")
        result["52w_low"] = info.get("fiftyTwoWeekLow")
        result["revenue_ttm"] = info.get("totalRevenue")
        result["profit_margin"] = info.get("profitMargins")
        result["employee_count"] = info.get("fullTimeEmployees")
        result["sector"] = info.get("sector")
        result["industry"] = info.get("industry")
        result["description"] = info.get("longBusinessSummary", "")[:500]

        # 30-day price history
        hist = ticker.history(period="1mo")
        if not hist.empty:
            prices = hist["Close"].tolist()
            dates = [str(d.date()) for d in hist.index]
            result["price_history_30d"] = [
                {"date": d, "close": round(p, 2)} for d, p in zip(dates, prices)
            ]
            if len(prices) >= 2:
                result["price_change_30d_pct"] = round(
                    ((prices[-1] - prices[0]) / prices[0]) * 100, 2
                )
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Yahoo Finance error for {company_name}: {e}")

    return result


def format_market_cap(value: int | None) -> str:
    if not value:
        return "N/A"
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    if value >= 1e9:
        return f"${value/1e9:.2f}B"
    if value >= 1e6:
        return f"${value/1e6:.2f}M"
    return f"${value:,}"
