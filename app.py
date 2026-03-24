"""
AI Competitor Intelligence - Enhanced with Real-Time Data Sources
Integrates: Yahoo Finance, NewsAPI, Google Trends, GitHub, SEC Edgar,
            Product Hunt, Crunchbase, Twitter/X, Job Boards
"""

import streamlit as st
import os
import json
import time
from datetime import datetime

# ─────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="AI Competitor Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────── CSS ─────────────────────────────────────
st.markdown(
    """
    <style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .metric-card {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 10px; padding: 16px; margin: 6px 0;
    }
    .source-badge {
        display: inline-block; background: #238636; color: #fff;
        border-radius: 12px; padding: 2px 10px; font-size: 0.75rem;
        font-weight: 600; margin: 2px;
    }
    .source-badge.warning { background: #d29922; }
    .source-badge.error   { background: #b62324; }
    .status-live   { color: #3fb950; font-weight: 700; }
    .status-cached { color: #d29922; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────── Sidebar ─────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("---")

    st.subheader("🔑 API Keys")
    groq_key = st.text_input(
        "Groq API Key *", type="password",
        value=os.getenv("GROQ_API_KEY", ""),
        help="Required. Get free at console.groq.com",
    )
    newsapi_key = st.text_input(
        "NewsAPI Key", type="password",
        value=os.getenv("NEWSAPI_KEY", ""),
        help="Optional. Get free at newsapi.org",
    )
    github_token = st.text_input(
        "GitHub Token", type="password",
        value=os.getenv("GITHUB_TOKEN", ""),
        help="Optional. Increases rate limits 60→5000 req/hr",
    )
    ph_key = st.text_input(
        "Product Hunt API Key", type="password",
        value=os.getenv("PH_API_KEY", ""),
        help="Optional. Register at producthunt.com/v2/oauth/applications",
    )
    ph_secret = st.text_input(
        "Product Hunt Secret", type="password",
        value=os.getenv("PH_API_SECRET", ""),
    )

    st.markdown("---")
    st.subheader("📡 Data Sources")

    col1, col2 = st.columns(2)
    with col1:
        use_yahoo    = st.checkbox("📈 Yahoo Finance", value=True)
        use_news     = st.checkbox("📰 NewsAPI",       value=True)
        use_trends   = st.checkbox("📊 Google Trends", value=True)
        use_github   = st.checkbox("💻 GitHub",        value=True)
        use_sec      = st.checkbox("📋 SEC Edgar",     value=True)
    with col2:
        use_ph       = st.checkbox("🚀 Product Hunt",  value=True)
        use_crunch   = st.checkbox("💰 Crunchbase",    value=True)
        use_twitter  = st.checkbox("🐦 Twitter/X",     value=True)
        use_jobs     = st.checkbox("👔 Job Boards",    value=True)

    st.markdown("---")
    st.subheader("🤖 AI Settings")
    groq_model = st.selectbox(
        "Model",
        ["llama-3.1-8b-instant", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"],
        index=0,
    )
    analysis_depth = st.select_slider(
        "Analysis Depth",
        options=["Quick", "Standard", "Deep"],
        value="Standard",
    )

# ─────────────────────────── Main UI ─────────────────────────────────
st.title("🔍 AI Competitor Intelligence")
st.caption("Real-time market research powered by 9 live data sources + AI synthesis")

# Set env vars from sidebar inputs (so scrapers pick them up)
if newsapi_key:
    os.environ["NEWSAPI_KEY"] = newsapi_key
if github_token:
    os.environ["GITHUB_TOKEN"] = github_token
if ph_key:
    os.environ["PH_API_KEY"] = ph_key
if ph_secret:
    os.environ["PH_API_SECRET"] = ph_secret

# Build source list
source_map = {
    "yahoo_finance": use_yahoo,
    "news":          use_news,
    "trends":        use_trends,
    "github":        use_github,
    "sec":           use_sec,
    "product_hunt":  use_ph,
    "crunchbase":    use_crunch,
    "twitter":       use_twitter,
    "jobs":          use_jobs,
}
enabled_sources = [k for k, v in source_map.items() if v]

# Input
col_input, col_btn = st.columns([4, 1])
with col_input:
    company = st.text_input(
        "Company to research",
        placeholder="e.g. Stripe, Notion, OpenAI, Shopify ...",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("🚀 Analyze", type="primary", use_container_width=True)

if not groq_key:
    st.warning("⚠️ Add your Groq API key in the sidebar to start analysis.")
    st.stop()

if not company:
    # Show data source overview
    st.markdown("### 📡 Connected Data Sources")
    source_info = [
        ("📈 Yahoo Finance",  "Stock price, market cap, financials", "Real-time", True),
        ("📰 NewsAPI",        "Latest news articles",                "Last 30 days", bool(newsapi_key)),
        ("📊 Google Trends",  "Search interest trends",              "Daily",      True),
        ("💻 GitHub API",     "Tech stack, repo activity",           "Real-time",  True),
        ("📋 SEC Edgar",      "Official 10-K / 10-Q filings",        "Real-time",  True),
        ("🚀 Product Hunt",   "Product launches & upvotes",          "Real-time",  bool(ph_key)),
        ("💰 Crunchbase",     "Funding rounds (public scrape)",       "Weekly",     True),
        ("🐦 Twitter/X",      "Real-time mentions via Nitter",        "Live",       True),
        ("👔 Job Boards",     "Hiring trends (Greenhouse + Lever)",   "Daily",      True),
    ]
    cols = st.columns(3)
    for i, (name, desc, freq, active) in enumerate(source_info):
        with cols[i % 3]:
            status = "🟢 Active" if active else "🟡 Needs API Key"
            st.markdown(
                f"""<div class="metric-card">
                <b>{name}</b><br>
                <small>{desc}</small><br>
                <small>🕒 {freq} &nbsp;|&nbsp; {status}</small>
                </div>""",
                unsafe_allow_html=True,
            )
    st.stop()

# ─────────────────────────── RUN ANALYSIS ─────────────────────────────
if run_btn and company:
    groq_client = _init_groq(groq_key, groq_model)
    if not groq_client:
        st.error("Failed to initialize Groq client. Check your API key.")
        st.stop()

    st.markdown(f"## 🔎 Analyzing: **{company}**")
    overall_progress = st.progress(0, text="Starting data collection...")
    status_container = st.empty()

    # ── Step 1: Collect Real-Time Data ──────────────────────────────
    status_container.info(f"📡 Collecting data from {len(enabled_sources)} sources in parallel...")
    t_start = time.time()

    from agents.realtime_agent import run_all_realtime_scrapers, build_llm_context
    raw_data = run_all_realtime_scrapers(company, enabled_sources=enabled_sources)
    llm_context = build_llm_context(raw_data)

    elapsed = round(time.time() - t_start, 1)
    overall_progress.progress(30, text=f"✅ Data collected in {elapsed}s")

    # Show quick data source status
    data = raw_data.get("data", {})
    badge_html = ""
    source_labels = {
        "yahoo_finance": "📈 Yahoo Finance",
        "news": "📰 NewsAPI",
        "trends": "📊 Trends",
        "github": "💻 GitHub",
        "sec": "📋 SEC",
        "product_hunt": "🚀 PH",
        "crunchbase": "💰 Crunchbase",
        "twitter": "🐦 Twitter",
        "jobs": "👔 Jobs",
    }
    for key, label in source_labels.items():
        if key not in data:
            continue
        src = data[key]
        if src.get("error"):
            badge_html += f'<span class="source-badge warning">{label} ⚠️</span>'
        else:
            badge_html += f'<span class="source-badge">{label} ✅</span>'

    st.markdown(f"**Data Sources:** {badge_html}", unsafe_allow_html=True)

    # ── Step 2: AI Analysis Tabs ─────────────────────────────────────
    overall_progress.progress(40, text="🤖 Running AI analysis...")

    tabs = st.tabs([
        "📊 Overview", "💰 Financials", "📰 News & Sentiment",
        "💻 Tech & GitHub", "🚀 Products & Launches",
        "👔 Hiring Intel", "⚔️ SWOT Analysis", "📋 Raw Data",
    ])

    depth_tokens = {"Quick": 400, "Standard": 800, "Deep": 1500}
    max_tok = depth_tokens[analysis_depth]

    def ai_section(system_prompt: str, user_prompt: str) -> str:
        """Call Groq LLM for a section of analysis."""
        try:
            resp = groq_client.chat.completions.create(
                model=groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tok,
                temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"⚠️ AI analysis failed: {e}"

    base_system = (
        "You are an expert competitive intelligence analyst. "
        "Analyze the provided real-time data and give actionable, specific insights. "
        "Be concise, data-driven, and highlight what matters most for competitive strategy. "
        "Use bullet points and emojis for readability. Ground every claim in the provided data."
    )

    # ── Tab 0: Overview ──────────────────────────────────────────────
    with tabs[0]:
        with st.spinner("Generating executive overview..."):
            overview = ai_section(
                base_system,
                f"Based on this real-time data, provide a 5-bullet executive summary of {company}'s "
                f"current market position, key strengths, threats, and one strategic recommendation:\n\n{llm_context}",
            )
        st.markdown(overview)

        # Quick metrics row
        yf = data.get("yahoo_finance", {})
        cb = data.get("crunchbase", {})
        gh = data.get("github", {})
        jobs_data = data.get("jobs", {})

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            price = yf.get("current_price")
            st.metric("Stock Price", f"${price:.2f}" if price else "Private", delta=f"{yf.get('price_change_30d_pct', 0):.1f}% (30d)" if price else None)
        with m2:
            from scrapers.yahoo_finance import format_market_cap
            mc = yf.get("market_cap") or None
            tf = cb.get("total_funding_formatted")
            st.metric("Market Cap / Funding", format_market_cap(mc) if mc else (tf or "N/A"))
        with m3:
            st.metric("GitHub Stars", f"{gh.get('total_stars', 0):,}" if gh.get("total_stars") else "N/A")
        with m4:
            open_roles = jobs_data.get("hiring_analysis", {}).get("total_open_roles", 0)
            st.metric("Open Roles", open_roles if open_roles else "N/A")

        overall_progress.progress(55)

    # ── Tab 1: Financials ────────────────────────────────────────────
    with tabs[1]:
        yf_data = data.get("yahoo_finance", {})
        cb_data = data.get("crunchbase", {})
        sec_data = data.get("sec", {})

        financial_context = f"Yahoo Finance: {json.dumps(yf_data, default=str)}\nCrunchbase: {json.dumps(cb_data, default=str)}\nSEC: {json.dumps(sec_data, default=str)}"

        with st.spinner("Analyzing financial data..."):
            fin_analysis = ai_section(
                base_system,
                f"Analyze the financial health and trajectory of {company} using this data. "
                f"Cover: valuation, growth signals, financial risks, and investment outlook.\n\n{financial_context}",
            )
        st.markdown(fin_analysis)

        # Stock chart if available
        price_hist = yf_data.get("price_history_30d", [])
        if price_hist:
            import pandas as pd
            df = pd.DataFrame(price_hist).set_index("date")
            st.line_chart(df["close"])

        # SEC filings table
        all_filings = (sec_data.get("recent_10k") or []) + (sec_data.get("recent_10q") or [])
        if all_filings:
            st.markdown("**Recent SEC Filings**")
            for f in all_filings[:6]:
                st.markdown(f"- **{f['form']}** | Filed: {f.get('filing_date', '')} | [View]({f.get('url', '#')})")

        overall_progress.progress(65)

    # ── Tab 2: News & Sentiment ──────────────────────────────────────
    with tabs[2]:
        news_d = data.get("news", {})
        tw_d = data.get("twitter", {})

        sentiment_context = f"News: {json.dumps(news_d, default=str)}\nTwitter: {json.dumps(tw_d, default=str)}"

        with st.spinner("Analyzing news and social sentiment..."):
            sentiment_analysis = ai_section(
                base_system,
                f"Analyze the news coverage and social media sentiment for {company}. "
                f"Identify key narratives, reputation signals, and emerging issues.\n\n{sentiment_context}",
            )
        st.markdown(sentiment_analysis)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📰 Latest News**")
            for art in (news_d.get("articles") or [])[:5]:
                st.markdown(f"- [{art.get('title', '')}]({art.get('url', '#')}) *{art.get('source', '')}*")

        with col2:
            st.markdown("**🐦 Top Social Mentions**")
            for t in (tw_d.get("top_tweets") or [])[:5]:
                st.markdown(f"- {t.get('text', '')[:120]} ❤️{t.get('likes', 0)}")

        overall_progress.progress(72)

    # ── Tab 3: Tech & GitHub ─────────────────────────────────────────
    with tabs[3]:
        gh_d = data.get("github", {})
        trends_d = data.get("trends", {})

        tech_context = f"GitHub: {json.dumps(gh_d, default=str)}\nTrends: {json.dumps(trends_d, default=str)}"

        with st.spinner("Analyzing tech stack and search trends..."):
            tech_analysis = ai_section(
                base_system,
                f"Analyze the technical profile and developer mindshare of {company}. "
                f"Cover: primary tech stack, open-source strategy, search interest trends, and developer perception.\n\n{tech_context}",
            )
        st.markdown(tech_analysis)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔧 Top Repositories**")
            for repo in (gh_d.get("top_repos") or [])[:5]:
                st.markdown(f"- [{repo.get('name', '')}]({repo.get('url', '#')}) ⭐{repo.get('stars', 0):,} | {repo.get('language', 'N/A')}")

        with col2:
            # Google Trends chart
            iot = trends_d.get("interest_over_time", [])
            if iot:
                import pandas as pd
                df = pd.DataFrame(iot).set_index("date")
                st.markdown("**📊 Search Interest (Google Trends)**")
                st.area_chart(df["interest"])

        overall_progress.progress(80)

    # ── Tab 4: Products & Launches ───────────────────────────────────
    with tabs[4]:
        ph_d = data.get("product_hunt", {})

        with st.spinner("Analyzing product launches..."):
            product_analysis = ai_section(
                base_system,
                f"Analyze {company}'s product launch history and reception on Product Hunt. "
                f"What does this tell us about their product strategy and market traction?\n\n{json.dumps(ph_d, default=str)}",
            )
        st.markdown(product_analysis)

        st.markdown("**🚀 Product Hunt Launches**")
        for prod in (ph_d.get("products") or [])[:8]:
            if not prod.get("name"):
                continue
            st.markdown(
                f"- **{prod.get('name', '')}** — {prod.get('tagline', '')} "
                f"| 👍 {prod.get('votes', 0)} votes"
                + (f" | [View]({prod.get('url', '')})" if prod.get("url") else "")
            )

        overall_progress.progress(87)

    # ── Tab 5: Hiring Intel ──────────────────────────────────────────
    with tabs[5]:
        jobs_d = data.get("jobs", {})

        with st.spinner("Analyzing hiring trends..."):
            hiring_analysis = ai_section(
                base_system,
                f"Analyze {company}'s hiring patterns. "
                f"What do their open roles reveal about strategic priorities, growth stage, and potential expansion areas?\n\n{json.dumps(jobs_d.get('hiring_analysis', {}), default=str)}",
            )
        st.markdown(hiring_analysis)

        ha = jobs_d.get("hiring_analysis", {})
        if ha:
            cols = st.columns(4)
            metrics = [
                ("Engineering", ha.get("engineering_roles", 0), "🔧"),
                ("Sales", ha.get("sales_roles", 0), "💼"),
                ("Marketing", ha.get("marketing_roles", 0), "📣"),
                ("Product", ha.get("product_roles", 0), "🎯"),
            ]
            for i, (label, val, icon) in enumerate(metrics):
                with cols[i]:
                    st.metric(f"{icon} {label}", val)

        overall_progress.progress(93)

    # ── Tab 6: SWOT ──────────────────────────────────────────────────
    with tabs[6]:
        with st.spinner("Generating comprehensive SWOT analysis..."):
            swot = ai_section(
                base_system,
                f"Generate a comprehensive SWOT analysis for {company} using ALL the real-time data provided. "
                f"Be highly specific — reference actual numbers, dates, and facts from the data. "
                f"Format: ## Strengths / ## Weaknesses / ## Opportunities / ## Threats\n\n{llm_context}",
            )
        st.markdown(swot)

        overall_progress.progress(98)

    # ── Tab 7: Raw Data ──────────────────────────────────────────────
    with tabs[7]:
        st.markdown("### 📦 Raw Scraped Data")
        for key, val in data.items():
            with st.expander(f"{source_labels.get(key, key)} — raw output"):
                st.json(val)

        st.markdown("---")
        st.download_button(
            "⬇️ Download All Raw Data (JSON)",
            data=json.dumps(raw_data, default=str, indent=2),
            file_name=f"{company.lower().replace(' ','_')}_intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )

    overall_progress.progress(100, text="✅ Analysis complete!")
    status_container.success(
        f"✅ Analyzed **{company}** using **{len(data)} data sources** | "
        f"Total time: {round(time.time() - t_start, 1)}s"
    )


# ─────────────────────────── Helpers ─────────────────────────────────
def _init_groq(api_key: str, model: str):
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        st.error("groq package not installed. Run: pip install groq")
        return None
    except Exception as e:
        st.error(f"Groq init error: {e}")
        return None
