"""
Advanced AI Competitor Intelligence — Real-Time Enhanced
9 free data sources: Yahoo Finance, Google News RSS, Google Trends,
GitHub, SEC Edgar, Product Hunt RSS, Wikipedia/Wikidata, Reddit, Job Boards
"""

import streamlit as st
import os
import json
import time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────
# HELPERS  (must be defined before anything calls them)
# ─────────────────────────────────────────────────────────────────────

def _init_groq(api_key: str, model: str):
    """Initialise and return a Groq client, or None on failure."""
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        st.error("groq package not installed. Run: pip install groq")
        return None
    except Exception as e:
        st.error(f"Groq init error: {e}")
        return None


def _ai_section(client, model: str, max_tokens: int,
                system_prompt: str, user_prompt: str) -> str:
    """Call Groq LLM and return the text response."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI analysis failed: {e}"


# ─────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Advanced AI Competitor Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-card {
    background: var(--background-color);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px; padding: 16px; margin: 6px 0;
}
.source-badge {
    display: inline-block; background: #238636; color: #fff;
    border-radius: 12px; padding: 2px 10px; font-size: 0.75rem;
    font-weight: 600; margin: 2px;
}
.source-badge.warn { background: #d29922; }
.source-badge.err  { background: #b62324; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuration")
    st.markdown("---")

    st.subheader("🔑 API Keys")
    groq_key = st.text_input(
        "Groq API Key *", type="password",
        value=os.getenv("GROQ_API_KEY", ""),
        help="Required — free at console.groq.com",
    )
    github_token = st.text_input(
        "GitHub Token", type="password",
        value=os.getenv("GITHUB_TOKEN", ""),
        help="Optional — raises rate limit 60→5000 req/hr",
    )

    st.markdown("---")
    st.subheader("📡 Data Sources")

    col1, col2 = st.columns(2)
    with col1:
        use_yahoo   = st.checkbox("📈 Yahoo Finance",  value=True)
        use_news    = st.checkbox("📰 Google News",    value=True)
        use_trends  = st.checkbox("📊 Trends",         value=True)
        use_github  = st.checkbox("💻 GitHub",         value=True)
        use_sec     = st.checkbox("📋 SEC Edgar",      value=True)
    with col2:
        use_ph      = st.checkbox("🚀 Product Hunt",   value=True)
        use_wiki    = st.checkbox("🏢 Wikipedia",      value=True)
        use_reddit  = st.checkbox("🗣️ Reddit",         value=True)
        use_jobs    = st.checkbox("👔 Job Boards",     value=True)

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


# ─────────────────────────────────────────────────────────────────────
# MAIN UI — header + input
# ─────────────────────────────────────────────────────────────────────

st.title("🔍 Advanced AI Competitor Intelligence")
st.caption("Real-time market research · 9 free data sources · AI synthesis")

# Push optional keys into env so scrapers can read them
if github_token:
    os.environ["GITHUB_TOKEN"] = github_token

# Map sidebar checkboxes → scraper keys
source_map = {
    "yahoo_finance": use_yahoo,
    "news":          use_news,
    "trends":        use_trends,
    "github":        use_github,
    "sec":           use_sec,
    "product_hunt":  use_ph,
    "crunchbase":    use_wiki,    # key name kept for scraper compatibility
    "twitter":       use_reddit,  # key name kept for scraper compatibility
    "jobs":          use_jobs,
}
enabled_sources = [k for k, v in source_map.items() if v]

# Human-readable labels for badges
SOURCE_LABELS = {
    "yahoo_finance": "📈 Yahoo Finance",
    "news":          "📰 Google News",
    "trends":        "📊 Trends",
    "github":        "💻 GitHub",
    "sec":           "📋 SEC Edgar",
    "product_hunt":  "🚀 Product Hunt",
    "crunchbase":    "🏢 Wikipedia",
    "twitter":       "🗣️ Reddit",
    "jobs":          "👔 Jobs",
}

col_input, col_btn = st.columns([4, 1])
with col_input:
    company = st.text_input(
        "Company",
        placeholder="e.g. Stripe, Notion, OpenAI, Shopify …",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("🚀 Analyse", type="primary", use_container_width=True)

# Gate: Groq key required
if not groq_key:
    st.warning("⚠️ Add your free Groq API key in the sidebar to start.")
    st.stop()

# Landing page — show source cards when no company entered
if not company:
    st.markdown("### 📡 Data Sources (all free, no keys)")
    source_cards = [
        ("📈 Yahoo Finance",   "Stock price, market cap, P/E",          "Real-time"),
        ("📰 Google News RSS", "Latest articles + sentiment",            "Continuous"),
        ("📊 Google Trends",   "Search interest & rising queries",       "Daily"),
        ("💻 GitHub API",      "Tech stack, stars, commit activity",     "Real-time"),
        ("📋 SEC Edgar",       "10-K / 10-Q filings (public cos.)",      "Real-time"),
        ("🚀 Product Hunt RSS","Product launches & upvotes",             "Continuous"),
        ("🏢 Wikipedia/Wikidata","Founded year, HQ, funding mentions",   "Continuous"),
        ("🗣️ Reddit",           "Community mentions & sentiment",         "Real-time"),
        ("👔 Greenhouse/Lever", "Open roles → hiring trends",            "Daily"),
    ]
    cols = st.columns(3)
    for i, (name, desc, freq) in enumerate(source_cards):
        with cols[i % 3]:
            st.markdown(
                f'<div class="metric-card"><b>{name}</b><br>'
                f'<small>{desc}</small><br>'
                f'<small>🕒 {freq} &nbsp;·&nbsp; 🟢 Free</small></div>',
                unsafe_allow_html=True,
            )
    st.stop()


# ─────────────────────────────────────────────────────────────────────
# RUN ANALYSIS
# ─────────────────────────────────────────────────────────────────────

if run_btn and company:

    # Initialise Groq client
    groq_client = _init_groq(groq_key, groq_model)
    if not groq_client:
        st.stop()

    depth_tokens = {"Quick": 400, "Standard": 800, "Deep": 1500}
    max_tok = depth_tokens[analysis_depth]

    BASE_SYSTEM = (
        "You are an expert competitive intelligence analyst. "
        "Analyse the provided real-time data and give actionable, specific insights. "
        "Be concise, data-driven, and ground every claim in the data provided. "
        "Use bullet points and emojis for readability."
    )

    st.markdown(f"## 🔎 Analysing: **{company}**")
    overall_progress = st.progress(0, text="Starting data collection…")
    status_box = st.empty()

    # ── Step 1: Parallel data collection ────────────────────────────
    status_box.info(f"📡 Collecting from {len(enabled_sources)} sources in parallel…")
    t_start = time.time()

    from agents.realtime_agent import run_all_realtime_scrapers, build_llm_context
    raw_data    = run_all_realtime_scrapers(company, enabled_sources=enabled_sources)
    llm_context = build_llm_context(raw_data)
    data        = raw_data.get("data", {})

    elapsed = round(time.time() - t_start, 1)
    overall_progress.progress(30, text=f"✅ Data collected in {elapsed}s")

    # Source status badges
    badge_html = ""
    for key, label in SOURCE_LABELS.items():
        if key not in data:
            continue
        css = "warn" if data[key].get("error") else ""
        icon = "⚠️" if css else "✅"
        badge_html += f'<span class="source-badge {css}">{label} {icon}</span>'
    st.markdown(badge_html, unsafe_allow_html=True)

    # ── Step 2: Analysis tabs ────────────────────────────────────────
    overall_progress.progress(40, text="🤖 Running AI analysis…")

    tabs = st.tabs([
        "📊 Overview", "💰 Financials", "📰 News & Sentiment",
        "💻 Tech & GitHub", "🚀 Products", "👔 Hiring Intel",
        "⚔️ SWOT", "📋 Raw Data",
    ])

    # Convenience wrapper with closed-over client / model / tokens
    def ai(system: str, prompt: str) -> str:
        return _ai_section(groq_client, groq_model, max_tok, system, prompt)

    # ── Tab 0: Overview ──────────────────────────────────────────────
    with tabs[0]:
        with st.spinner("Generating executive overview…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Give a 5-bullet executive summary of {company}'s current market position, "
                f"key strengths, main threats, and one strategic recommendation:\n\n{llm_context}",
            ))

        yf        = data.get("yahoo_finance", {})
        cb        = data.get("crunchbase", {})
        gh        = data.get("github", {})
        jobs_data = data.get("jobs", {})

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            price = yf.get("current_price")
            chg   = yf.get("price_change_30d_pct", 0)
            st.metric("Stock Price",
                      f"${price:.2f}" if price else "Private",
                      delta=f"{chg:.1f}% (30d)" if price else None)
        with m2:
            from scrapers.yahoo_finance import format_market_cap
            mc = yf.get("market_cap")
            tf = cb.get("total_funding_formatted")
            st.metric("Market Cap / Funding",
                      format_market_cap(mc) if mc else (tf or "N/A"))
        with m3:
            stars = gh.get("total_stars", 0)
            st.metric("GitHub Stars", f"{stars:,}" if stars else "N/A")
        with m4:
            open_roles = jobs_data.get("hiring_analysis", {}).get("total_open_roles", 0)
            st.metric("Open Roles", open_roles or "N/A")

        overall_progress.progress(55)

    # ── Tab 1: Financials ────────────────────────────────────────────
    with tabs[1]:
        yf_data  = data.get("yahoo_finance", {})
        cb_data  = data.get("crunchbase", {})
        sec_data = data.get("sec", {})

        fin_ctx = (
            f"Yahoo Finance: {json.dumps(yf_data, default=str)}\n"
            f"Company data: {json.dumps(cb_data, default=str)}\n"
            f"SEC filings: {json.dumps(sec_data, default=str)}"
        )
        with st.spinner("Analysing financial data…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Analyse the financial health and trajectory of {company}. "
                f"Cover: valuation, growth signals, financial risks, investment outlook.\n\n{fin_ctx}",
            ))

        price_hist = yf_data.get("price_history_30d", [])
        if price_hist:
            import pandas as pd
            df = pd.DataFrame(price_hist).set_index("date")
            st.line_chart(df["close"])

        filings = (sec_data.get("recent_10k") or []) + (sec_data.get("recent_10q") or [])
        if filings:
            st.markdown("**Recent SEC Filings**")
            for f in filings[:6]:
                st.markdown(
                    f"- **{f['form']}** | {f.get('filing_date','')} | "
                    f"[View filing]({f.get('url','#')})"
                )
        overall_progress.progress(65)

    # ── Tab 2: News & Sentiment ──────────────────────────────────────
    with tabs[2]:
        news_d   = data.get("news", {})
        reddit_d = data.get("twitter", {})   # key kept for compat

        sent_ctx = (
            f"News: {json.dumps(news_d, default=str)}\n"
            f"Reddit: {json.dumps(reddit_d, default=str)}"
        )
        with st.spinner("Analysing news and social sentiment…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Analyse news coverage and community sentiment for {company}. "
                f"Identify key narratives, reputation signals, and emerging issues.\n\n{sent_ctx}",
            ))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📰 Latest News**")
            for art in (news_d.get("articles") or [])[:6]:
                title = art.get("title", "")
                url   = art.get("url", "#")
                src   = art.get("source", "")
                st.markdown(f"- [{title}]({url}) *{src}*")
        with c2:
            st.markdown("**🗣️ Top Reddit Discussions**")
            for t in (reddit_d.get("top_tweets") or [])[:6]:
                text = (t.get("text") or "")[:120]
                likes = t.get("likes", 0)
                st.markdown(f"- {text} 👍{likes}")

        overall_progress.progress(72)

    # ── Tab 3: Tech & GitHub ─────────────────────────────────────────
    with tabs[3]:
        gh_d     = data.get("github", {})
        trends_d = data.get("trends", {})

        tech_ctx = (
            f"GitHub: {json.dumps(gh_d, default=str)}\n"
            f"Trends: {json.dumps(trends_d, default=str)}"
        )
        with st.spinner("Analysing tech stack and search trends…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Analyse the technical profile and developer mindshare of {company}. "
                f"Cover: tech stack, open-source strategy, search trends, developer perception.\n\n{tech_ctx}",
            ))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🔧 Top Repositories**")
            for repo in (gh_d.get("top_repos") or [])[:5]:
                name  = repo.get("name", "")
                url   = repo.get("url", "#")
                stars = repo.get("stars", 0)
                lang  = repo.get("language", "N/A")
                st.markdown(f"- [{name}]({url}) ⭐{stars:,} · {lang}")
        with c2:
            iot = trends_d.get("interest_over_time", [])
            if iot:
                import pandas as pd
                df = pd.DataFrame(iot).set_index("date")
                st.markdown("**📊 Search Interest (Google Trends)**")
                st.area_chart(df["interest"])

        overall_progress.progress(80)

    # ── Tab 4: Products ──────────────────────────────────────────────
    with tabs[4]:
        ph_d = data.get("product_hunt", {})

        with st.spinner("Analysing product launches…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Analyse {company}'s Product Hunt history. What does it reveal about "
                f"product strategy and market traction?\n\n{json.dumps(ph_d, default=str)}",
            ))

        st.markdown("**🚀 Product Hunt Launches**")
        for prod in (ph_d.get("products") or [])[:8]:
            if not prod.get("name"):
                continue
            name    = prod.get("name", "")
            tagline = prod.get("tagline", "")
            votes   = prod.get("votes", 0)
            url     = prod.get("url", "")
            line = f"- **{name}** — {tagline} | 👍 {votes} votes"
            if url:
                line += f" | [View]({url})"
            st.markdown(line)

        overall_progress.progress(87)

    # ── Tab 5: Hiring Intel ──────────────────────────────────────────
    with tabs[5]:
        jobs_d = data.get("jobs", {})
        ha     = jobs_d.get("hiring_analysis", {})

        with st.spinner("Analysing hiring trends…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Analyse {company}'s hiring patterns. What do open roles reveal about "
                f"strategic priorities and growth stage?\n\n{json.dumps(ha, default=str)}",
            ))

        if ha:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🔧 Engineering", ha.get("engineering_roles", 0))
            c2.metric("💼 Sales",       ha.get("sales_roles", 0))
            c3.metric("📣 Marketing",   ha.get("marketing_roles", 0))
            c4.metric("🎯 Product",     ha.get("product_roles", 0))

            if ha.get("inferred_growth_phase"):
                st.info(f"**Growth phase:** {ha['inferred_growth_phase']}")
            if ha.get("remote_roles"):
                st.caption(f"🏠 Remote roles: {ha['remote_roles']}")

        overall_progress.progress(93)

    # ── Tab 6: SWOT ──────────────────────────────────────────────────
    with tabs[6]:
        with st.spinner("Generating SWOT analysis…"):
            st.markdown(ai(
                BASE_SYSTEM,
                f"Generate a comprehensive SWOT analysis for {company} using ALL the data below. "
                f"Be specific — cite actual numbers, dates, and facts. "
                f"Format as: ## Strengths / ## Weaknesses / ## Opportunities / ## Threats\n\n{llm_context}",
            ))
        overall_progress.progress(98)

    # ── Tab 7: Raw Data ──────────────────────────────────────────────
    with tabs[7]:
        st.markdown("### 📦 Raw Scraped Data")
        for key, val in data.items():
            label = SOURCE_LABELS.get(key, key)
            with st.expander(f"{label} — raw JSON"):
                st.json(val)

        st.markdown("---")
        st.download_button(
            label="⬇️ Download Full Report (JSON)",
            data=json.dumps(raw_data, default=str, indent=2),
            file_name=(
                f"{company.lower().replace(' ', '_')}_intelligence_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            ),
            mime="application/json",
        )

    # ── Done ─────────────────────────────────────────────────────────
    overall_progress.progress(100, text="✅ Analysis complete!")
    status_box.success(
        f"✅ **{company}** analysed across **{len(data)} sources** in "
        f"{round(time.time() - t_start, 1)}s"
    )
