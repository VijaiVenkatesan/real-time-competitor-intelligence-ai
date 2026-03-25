"""
Google Trends Scraper - Search interest trends (daily)
Uses: pytrends (unofficial Google Trends API wrapper) - no API key needed
"""

import warnings
import logging
from datetime import datetime

# Suppress the pandas FutureWarning that pytrends triggers on fillna
warnings.filterwarnings("ignore", category=FutureWarning, module="pytrends")

import pandas as pd
pd.set_option("future.no_silent_downcasting", True)

logger = logging.getLogger(__name__)


def get_trends_data(company_name: str, timeframe: str = "today 3-m") -> dict:
    """
    Fetch Google Trends search interest for a company.
    timeframe options: 'today 1-m', 'today 3-m', 'today 12-m'
    Returns interest over time and related queries.
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

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(
            [company_name], cat=0, timeframe=timeframe, geo="", gprop=""
        )

        # Interest over time
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            iot = pytrends.interest_over_time()

        if not iot.empty and company_name in iot.columns:
            # Use infer_objects to avoid silent downcasting deprecation
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

            # Trend direction: compare first half vs second half
            mid          = len(values) // 2
            first_half   = sum(values[:mid]) / mid if mid else 0
            second_half  = (
                sum(values[mid:]) / (len(values) - mid)
                if (len(values) - mid) else 0
            )
            if second_half > first_half * 1.1:
                result["trend_direction"] = "Rising"
            elif second_half < first_half * 0.9:
                result["trend_direction"] = "Declining"
            else:
                result["trend_direction"] = "Stable"

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

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Google Trends error for {company_name}: {e}")

    return result
