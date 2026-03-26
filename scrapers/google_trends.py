"""
Google Trends Scraper - Search interest trends (daily)
Uses: pytrends (unofficial Google Trends API wrapper) - no API key needed

Google returns 429 when Streamlit Cloud's shared IP hits rate limits.
Strategy: retry up to 3 times with exponential backoff + random jitter.
"""

import time
import random
import warnings
import logging
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning, module="pytrends")

import pandas as pd
pd.set_option("future.no_silent_downcasting", True)

logger = logging.getLogger(__name__)

MAX_RETRIES   = 3
BASE_DELAY    = 5   # seconds before first retry
MAX_DELAY     = 30  # cap on wait time


def get_trends_data(company_name: str, timeframe: str = "today 3-m") -> dict:
    """
    Fetch Google Trends search interest for a company.
    Retries on 429 with exponential backoff.
    """
    result = {
        "source": "Google Trends",
        "company": company_name,
        "fetched_at": datetime.utcnow().isoformat(),
        "timeframe": timeframe,
        "interest_over_time": [],
        "average_interest": None,
        "peak_interest": None,
        "trend_direction": None,
        "related_queries_rising": [],
        "related_queries_top": [],
        "error": None,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(
                hl="en-US",
                tz=330,           # IST offset for Indian companies (330 = UTC+5:30)
                timeout=(10, 30),
                retries=1,
                backoff_factor=0.5,
            )
            pytrends.build_payload(
                [company_name],
                cat=0,
                timeframe=timeframe,
                geo="",
                gprop="",
            )

            # Interest over time
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                iot = pytrends.interest_over_time()

            if not iot.empty and company_name in iot.columns:
                iot = iot.infer_objects(copy=False)
                values = iot[company_name].tolist()
                dates  = [str(d.date()) for d in iot.index]

                result["interest_over_time"] = [
                    {"date": d, "interest": v} for d, v in zip(dates, values)
                ]
                result["average_interest"] = (
                    round(sum(values) / len(values), 1) if values else 0
                )
                result["peak_interest"] = max(values) if values else 0

                mid = len(values) // 2
                first_half  = sum(values[:mid]) / mid if mid else 0
                second_half = (
                    sum(values[mid:]) / (len(values) - mid)
                    if (len(values) - mid) else 0
                )
                if second_half > first_half * 1.1:
                    result["trend_direction"] = "Rising 📈"
                elif second_half < first_half * 0.9:
                    result["trend_direction"] = "Declining 📉"
                else:
                    result["trend_direction"] = "Stable ➡️"

            # Related queries
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                related = pytrends.related_queries()

            if company_name in related:
                rising = related[company_name].get("rising")
                top    = related[company_name].get("top")
                if rising is not None and not rising.empty:
                    result["related_queries_rising"] = (
                        rising.head(10)["query"].tolist()
                    )
                if top is not None and not top.empty:
                    result["related_queries_top"] = (
                        top.head(10)["query"].tolist()
                    )

            # Success — clear any error and return
            result.pop("error", None)
            result["error"] = None
            return result

        except Exception as e:
            last_error = str(e)
            err_lower  = last_error.lower()

            if "429" in last_error or "response code" in err_lower or "too many" in err_lower:
                if attempt < MAX_RETRIES - 1:
                    wait = min(BASE_DELAY * (2 ** attempt) + random.uniform(1, 3), MAX_DELAY)
                    logger.warning(
                        f"Google Trends 429 for '{company_name}' "
                        f"(attempt {attempt + 1}/{MAX_RETRIES}), "
                        f"retrying in {wait:.1f}s…"
                    )
                    time.sleep(wait)
                    continue
                else:
                    result["error"] = (
                        "Google Trends rate-limited (429) on Streamlit Cloud's shared IP. "
                        "This is temporary — re-run in 1–2 minutes. "
                        "Trend data unavailable for this run."
                    )
            else:
                result["error"] = f"Google Trends error: {last_error}"
                logger.error(f"Google Trends non-429 error for '{company_name}': {last_error}")
                break

    if result.get("error") is None:
        result["error"] = f"Google Trends failed after {MAX_RETRIES} attempts: {last_error}"

    return result
