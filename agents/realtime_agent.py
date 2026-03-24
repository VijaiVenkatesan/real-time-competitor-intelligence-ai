"""
Real-Time Intelligence Agent
Orchestrates all new data source scrapers and synthesizes the results via LLM.
"""

import concurrent.futures
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def run_all_realtime_scrapers(company_name: str, enabled_sources: list[str] | None = None) -> dict:
    """
    Run all real-time data scrapers in parallel and return combined raw data.
    
    enabled_sources: list of source names to enable. None = all sources.
    Available: ['yahoo_finance', 'news', 'trends', 'github', 'sec', 'product_hunt', 'crunchbase', 'twitter', 'jobs']
    """
    all_sources = {
        "yahoo_finance": _fetch_yahoo_finance,
        "news": _fetch_news,
        "trends": _fetch_trends,
        "github": _fetch_github,
        "sec": _fetch_sec,
        "product_hunt": _fetch_product_hunt,
        "crunchbase": _fetch_crunchbase,
        "twitter": _fetch_twitter,
        "jobs": _fetch_jobs,
    }

    if enabled_sources:
        sources = {k: v for k, v in all_sources.items() if k in enabled_sources}
    else:
        sources = all_sources

    results = {}
    errors = {}

    # Run all scrapers in parallel (max 6 threads to be polite)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_key = {
            executor.submit(fn, company_name): key
            for key, fn in sources.items()
        }
        for future in concurrent.futures.as_completed(future_to_key, timeout=60):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                errors[key] = str(e)
                logger.error(f"Scraper {key} failed: {e}")

    return {
        "company": company_name,
        "scraped_at": datetime.utcnow().isoformat(),
        "data": results,
        "errors": errors,
    }


def _fetch_yahoo_finance(company_name: str) -> dict:
    from scrapers.yahoo_finance import get_financial_data
    return get_financial_data(company_name)


def _fetch_news(company_name: str) -> dict:
    from scrapers.newsapi_scraper import get_company_news
    return get_company_news(company_name)


def _fetch_trends(company_name: str) -> dict:
    from scrapers.google_trends import get_trends_data
    return get_trends_data(company_name)


def _fetch_github(company_name: str) -> dict:
    from scrapers.github_scraper import get_github_data
    return get_github_data(company_name)


def _fetch_sec(company_name: str) -> dict:
    from scrapers.sec_edgar import get_sec_filings
    return get_sec_filings(company_name)


def _fetch_product_hunt(company_name: str) -> dict:
    from scrapers.product_hunt import get_product_hunt_data
    return get_product_hunt_data(company_name)


def _fetch_crunchbase(company_name: str) -> dict:
    from scrapers.crunchbase_scraper import get_funding_data
    return get_funding_data(company_name)


def _fetch_twitter(company_name: str) -> dict:
    from scrapers.twitter_scraper import get_twitter_mentions
    return get_twitter_mentions(company_name)


def _fetch_jobs(company_name: str) -> dict:
    from scrapers.job_boards import get_job_board_data
    return get_job_board_data(company_name)


def build_llm_context(raw_data: dict) -> str:
    """Convert raw scraped data into a structured context string for the LLM."""
    company = raw_data.get("company", "Unknown")
    data = raw_data.get("data", {})
    lines = [f"# Real-Time Intelligence Data for: {company}", f"Scraped at: {raw_data.get('scraped_at', '')}", ""]

    # Yahoo Finance
    if yf := data.get("yahoo_finance"):
        lines.append("## 📈 Stock & Financial Data (Yahoo Finance)")
        if not yf.get("error"):
            lines.append(f"- Ticker: {yf.get('ticker', 'N/A')}")
            lines.append(f"- Current Price: {yf.get('currency','$')}{yf.get('current_price', 'N/A')}")
            from scrapers.yahoo_finance import format_market_cap
            lines.append(f"- Market Cap: {format_market_cap(yf.get('market_cap'))}")
            lines.append(f"- P/E Ratio: {yf.get('pe_ratio', 'N/A')}")
            lines.append(f"- 30-Day Price Change: {yf.get('price_change_30d_pct', 'N/A')}%")
            lines.append(f"- Revenue (TTM): {format_market_cap(yf.get('revenue_ttm'))}")
            lines.append(f"- Profit Margin: {yf.get('profit_margin', 'N/A')}")
            lines.append(f"- Sector: {yf.get('sector', 'N/A')} | Industry: {yf.get('industry', 'N/A')}")
            lines.append(f"- Employees: {yf.get('employee_count', 'N/A')}")
        else:
            lines.append(f"- Note: {yf.get('error')} (may be private company)")
        lines.append("")

    # News
    if news := data.get("news"):
        lines.append("## 📰 Latest News (NewsAPI)")
        if not news.get("error"):
            lines.append(f"- Total Results: {news.get('total_results', 0)}")
            sentiment = news.get("sentiment_summary", {})
            lines.append(f"- News Sentiment: {sentiment.get('label', 'N/A')} (+{sentiment.get('positive_signals',0)} / -{sentiment.get('negative_signals',0)})")
            for art in (news.get("articles") or [])[:5]:
                lines.append(f"  • [{art.get('source','')}] {art.get('title','')} ({art.get('published_at','')[:10]})")
        else:
            lines.append(f"- Note: {news.get('error')}")
        lines.append("")

    # Google Trends
    if trends := data.get("trends"):
        lines.append("## 📊 Google Trends")
        if not trends.get("error"):
            lines.append(f"- Average Interest (0-100): {trends.get('average_interest', 'N/A')}")
            lines.append(f"- Peak Interest: {trends.get('peak_interest', 'N/A')}")
            lines.append(f"- Trend Direction: {trends.get('trend_direction', 'N/A')}")
            rising = trends.get("related_queries_rising", [])
            if rising:
                lines.append(f"- Rising Queries: {', '.join(rising[:5])}")
        else:
            lines.append(f"- Note: {trends.get('error')}")
        lines.append("")

    # GitHub
    if gh := data.get("github"):
        lines.append("## 💻 GitHub / Tech Stack")
        if not gh.get("error"):
            lines.append(f"- Org: github.com/{gh.get('org_handle', 'N/A')}")
            lines.append(f"- Public Repos: {gh.get('total_public_repos', 'N/A')}")
            lines.append(f"- Total Stars: {gh.get('total_stars', 0):,}")
            lines.append(f"- Open Source Presence: {gh.get('open_source_presence', 'N/A')}")
            langs = gh.get("top_languages", [])
            if langs:
                lines.append(f"- Primary Languages: {', '.join(langs)}")
            activity = gh.get("recent_activity")
            if activity:
                lines.append(f"- Commits (last 30d on top repo): {activity.get('commits_last_30d', 'N/A')}")
        else:
            lines.append(f"- Note: {gh.get('error')}")
        lines.append("")

    # SEC Edgar
    if sec := data.get("sec"):
        lines.append("## 📋 SEC Filings (Edgar)")
        if not sec.get("error"):
            lines.append(f"- CIK: {sec.get('cik', 'N/A')}")
            for f in (sec.get("recent_10k") or [])[:2]:
                lines.append(f"  • 10-K filed: {f.get('filing_date', '')} — {f.get('url', '')}")
            for f in (sec.get("recent_10q") or [])[:2]:
                lines.append(f"  • 10-Q filed: {f.get('filing_date', '')} — {f.get('url', '')}")
        else:
            lines.append(f"- Note: {sec.get('error')}")
        lines.append("")

    # Product Hunt
    if ph := data.get("product_hunt"):
        lines.append("## 🚀 Product Hunt")
        if not ph.get("error") or ph.get("products"):
            lines.append(f"- Total Upvotes Across Products: {ph.get('total_upvotes', 0)}")
            top = ph.get("top_product")
            if top:
                lines.append(f"- Top Product: {top.get('name')} ({top.get('votes', 0)} votes) - {top.get('tagline', '')}")
            recent = ph.get("most_recent_launch")
            if recent and recent != top:
                lines.append(f"- Most Recent Launch: {recent.get('name')} ({recent.get('launched_at', '')[:10]})")
        else:
            lines.append(f"- Note: {ph.get('error')}")
        lines.append("")

    # Crunchbase
    if cb := data.get("crunchbase"):
        lines.append("## 💰 Funding Data (Crunchbase)")
        if not cb.get("error"):
            lines.append(f"- Total Funding: {cb.get('total_funding_formatted', 'N/A')}")
            lines.append(f"- Funding Rounds: {cb.get('funding_rounds', 'N/A')}")
            lines.append(f"- Last Funding: {cb.get('last_funding_date', 'N/A')} ({cb.get('last_funding_type', 'N/A')})")
            lines.append(f"- Investors: {cb.get('investor_count', 'N/A')}")
            lines.append(f"- Founded: {cb.get('founded_year', 'N/A')}")
            lines.append(f"- Employee Range: {cb.get('employee_range', 'N/A')}")
        else:
            lines.append(f"- Note: {cb.get('error')}")
        lines.append("")

    # Twitter
    if tw := data.get("twitter"):
        lines.append("## 🐦 Twitter/X Mentions")
        if not tw.get("error"):
            lines.append(f"- Tweets Analyzed: {tw.get('total_scraped', 0)}")
            sentiment = tw.get("sentiment", {})
            if sentiment:
                lines.append(f"- Social Sentiment: {sentiment.get('sentiment_label', 'N/A')}")
                lines.append(f"  Positive: {sentiment.get('positive_pct', 0)}% | Negative: {sentiment.get('negative_pct', 0)}%")
            for t in (tw.get("top_tweets") or [])[:3]:
                lines.append(f"  • {t.get('text', '')[:120]}... (❤️ {t.get('likes',0)})")
        else:
            lines.append(f"- Note: {tw.get('error')}")
        lines.append("")

    # Jobs
    if jobs := data.get("jobs"):
        lines.append("## 👔 Hiring Trends (Job Boards)")
        analysis = jobs.get("hiring_analysis", {})
        if analysis:
            lines.append(f"- Open Roles: {analysis.get('total_open_roles', 0)}")
            lines.append(f"- Engineering: {analysis.get('engineering_roles', 0)} | Sales: {analysis.get('sales_roles', 0)} | Marketing: {analysis.get('marketing_roles', 0)} | Product: {analysis.get('product_roles', 0)}")
            lines.append(f"- Remote Roles: {analysis.get('remote_roles', 0)}")
            lines.append(f"- Growth Phase: {analysis.get('inferred_growth_phase', 'N/A')}")
            top_depts = analysis.get("top_departments", [])
            if top_depts:
                lines.append(f"- Top Departments: {', '.join(d[0] for d in top_depts[:3])}")
        elif jobs.get("error"):
            lines.append(f"- Note: {jobs.get('error')}")
        lines.append("")

    return "\n".join(lines)
