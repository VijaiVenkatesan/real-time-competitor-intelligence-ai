"""
AI Competitor Intelligence — Real-Time Enhanced
All API keys read from Streamlit Cloud secrets (never shown in UI).
9 free data sources: Yahoo Finance, Google News RSS, Google Trends,
GitHub, SEC Edgar, Product Hunt RSS, Wikipedia/Wikidata, Reddit, Job Boards
"""

import streamlit as st
import os
import json
import time
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning, module="pytrends")

import pandas as pd
pd.set_option("future.no_silent_downcasting", True)


# ─────────────────────────────────────────────────────────────────────
# SECRETS
# ─────────────────────────────────────────────────────────────────────

def _get_secret(key: str) -> str:
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")


GROQ_API_KEY = _get_secret("GROQ_API_KEY")
GITHUB_TOKEN = _get_secret("GITHUB_TOKEN")

if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY
if GITHUB_TOKEN:
    os.environ["GITHUB_TOKEN"] = GITHUB_TOKEN


# ─────────────────────────────────────────────────────────────────────
# GROQ MODELS — current active models only (March 2026)
# Decommissioned: llama-3.1-70b-versatile, mixtral-8x7b-32768
# ─────────────────────────────────────────────────────────────────────

GROQ_MODELS = {
    "llama-3.1-8b-instant":                          "Llama 3.1 8B  ⚡ Fastest (production)",
    "llama-3.3-70b-versatile":                        "Llama 3.3 70B 🧠 Best quality (production)",
    "meta-llama/llama-4-scout-17b-16e-instruct":      "Llama 4 Scout 17B 🦅 (preview)",
    "meta-llama/llama-4-maverick-17b-128e-instruct":  "Llama 4 Maverick 17B 🚀 (preview)",
    "qwen/qwen-3-32b":                                "Qwen 3 32B 🌏 (preview)",
}

# Token limits per model — Groq enforces per-model maximums
# Keep well below the hard ceiling to avoid truncation errors
MODEL_MAX_TOKENS = {
    "llama-3.1-8b-instant":                          8000,
    "llama-3.3-70b-versatile":                        8000,
    "meta-llama/llama-4-scout-17b-16e-instruct":      8000,
    "meta-llama/llama-4-maverick-17b-128e-instruct":  8000,
    "qwen/qwen-3-32b":                                8000,
}

# Tokens per analysis section based on depth setting
DEPTH_TOKENS = {
    "Quick":    1200,
    "Standard": 2000,
    "Deep":     4000,
}


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

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


def _ai_section(client, model: str, max_tokens: int,
                system_prompt: str, user_prompt: str) -> str:
    """
    Call Groq LLM. Caps max_tokens to the model's known limit.
    Uses temperature=0.3 for factual, grounded analysis.
    """
    cap = MODEL_MAX_TOKENS.get(model, 8000)
    actual_tokens = min(max_tokens, cap)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=actual_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        err = str(e)
        if "decommissioned" in err or "model_decommissioned" in err:
            return (
                f"⚠️ **Model `{model}` has been decommissioned by Groq.**\n\n"
                "Please select a different model from the sidebar."
            )
        if "rate_limit" in err.lower() or "429" in err:
            return (
                "⚠️ **Groq rate limit hit.** Please wait 30 seconds and try again, "
                "or switch to a faster model (Llama 3.1 8B) in the sidebar."
            )
        return f"⚠️ AI analysis failed: {err}"


# ─────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Competitor Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-card {
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
        options=list(GROQ_MODELS.keys()),
        format_func=lambda x: GROQ_MODELS[x],
        index=0,
    )

    analysis_depth = st.select_slider(
        "Analysis Depth",
        options=["Quick", "Standard", "Deep"],
        value="Standard",
    )

    # Show token budget info
    toks = DEPTH_TOKENS[analysis_depth]
    st.caption(f"📝 {toks:,} tokens per section · {toks * 7} tabs ≈ {toks * 7:,} total")

    st.markdown("---")
    st.caption("🔒 API keys stored in Streamlit Cloud secrets — not shown here.")


# ─────────────────────────────────────────────────────────────────────
# MAIN UI
# ─────────────────────────────────────────────────────────────────────

st.title("🔍 AI Real Time Competitor Intelligence")
st.caption("Real-time market research · 9 free data sources · AI synthesis")

if not GROQ_API_KEY:
    st.error(
        "**GROQ_API_KEY not found in Streamlit secrets.**\n\n"
        "Go to your app → ⋮ → **Settings → Secrets** and add:\n"
        "```toml\nGROQ_API_KEY = \"gsk_your_key_here\"\n```\n"
        "Get a free key at [console.groq.com](https://console.groq.com)"
    )
    st.stop()

source_map = {
    "yahoo_finance": use_yahoo,
    "news":          use_news,
    "trends":        use_trends,
    "github":        use_github,
    "sec":           use_sec,
    "product_hunt":  use_ph,
    "crunchbase":    use_wiki,
    "twitter":       use_reddit,
    "jobs":          use_jobs,
}
enabled_sources = [k for k, v in source_map.items() if v]

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

if not company:
    st.markdown("### 📡 Data Sources — all free, no keys")
    source_cards = [
        ("📈 Yahoo Finance",     "Stock price, market cap, P/E",          "Real-time"),
        ("📰 Google News RSS",   "Latest articles + sentiment",            "Continuous"),
        ("📊 Google Trends",     "Search interest & rising queries",       "Daily"),
        ("💻 GitHub API",        "Tech stack, stars, commit activity",     "Real-time"),
        ("📋 SEC Edgar",         "10-K / 10-Q filings (public cos.)",      "Real-time"),
        ("🚀 Product Hunt RSS",  "Product launches & upvotes",             "Continuous"),
        ("🏢 Wikipedia/Wikidata","Founded year, HQ, funding mentions",     "Continuous"),
        ("🗣️ Reddit",             "Community mentions & sentiment",         "Real-time"),
        ("👔 Greenhouse/Lever",  "Open roles → hiring trends",             "Daily"),
    ]
    cols = st.columns(3)
    for i, (name, desc, freq) in enumerate(source_cards):
        with cols[i % 3]:
            st.markdown(
                f'<div class="metric-card"><b>{name}</b><br>'
                f'<small>{desc}</small><br>'
                f'<small>🕒 {freq} &nbsp;·&nbsp; 🟢 Free · No key</small></div>',
                unsafe_allow_html=True,
            )
    st.stop()


# ─────────────────────────────────────────────────────────────────────
# RUN ANALYSIS
# ─────────────────────────────────────────────────────────────────────

if run_btn and company:

    groq_client = _init_groq(GROQ_API_KEY, groq_model)
    if not groq_client:
        st.stop()

    max_tok = DEPTH_TOKENS[analysis_depth]

    BASE_SYSTEM = (
        "You are an expert competitive intelligence analyst. "
        "Analyse the provided real-time data and give thorough, complete, actionable insights. "
        "IMPORTANT: Always write complete sentences and complete all sections fully — "
        "never stop mid-sentence or leave a section unfinished. "
        "Be data-driven and ground every claim in the provided data. "
        "Use bullet points, bold text, and emojis for readability."
    )

    st.markdown(f"## 🔎 Analysing: **{company}**")
    overall_progress = st.progress(0, text="Starting data collection…")
    status_box = st.empty()

    # ── Step 1: Data collection ──────────────────────────────────────
    status_box.info(f"📡 Collecting from {len(enabled_sources)} sources in parallel…")
    t_start = time.time()

    from agents.realtime_agent import run_all_realtime_scrapers, build_llm_context
    raw_data    = run_all_realtime_scrapers(company, enabled_sources=enabled_sources)
    llm_context = build_llm_context(raw_data)
    data        = raw_data.get("data", {})

    elapsed = round(time.time() - t_start, 1)
    overall_progress.progress(30, text=f"✅ Data collected in {elapsed}s")

    # Source badges
    badge_html = ""
    for key, label in SOURCE_LABELS.items():
        if key not in data:
            continue
        src     = data[key]
        has_err = bool(src.get("error"))
        # For Yahoo Finance: rate limit is temporary, show different colour
        yf_rate_limited = (
            key == "yahoo_finance"
            and has_err
            and "rate" in (src.get("error") or "").lower()
        )
        if yf_rate_limited:
            badge_html += f'<span class="source-badge warn">{label} 🔄</span>'
        elif has_err:
            badge_html += f'<span class="source-badge warn">{label} ⚠️</span>'
        else:
            badge_html += f'<span class="source-badge">{label} ✅</span>'
    st.markdown(badge_html, unsafe_allow_html=True)

    # Show Yahoo rate-limit note if triggered
    yf_data = data.get("yahoo_finance", {})
    if yf_data.get("error") and "rate" in (yf_data.get("error") or "").lower():
        st.warning(
            "⏱️ **Yahoo Finance is rate-limiting requests from Streamlit Cloud's shared IP.** "
            "Stock/market cap data may be unavailable this run. "
            "All other sources are unaffected — re-run in ~60s to get financial data."
        )

    overall_progress.progress(40, text="🤖 Running AI analysis…")

    tabs = st.tabs([
        "📊 Overview", "💰 Financials", "📰 News & Sentiment",
        "💻 Tech & GitHub", "🚀 Products", "👔 Hiring Intel",
        "⚔️ SWOT", "📋 Raw Data",
    ])

    def ai(system: str, prompt: str) -> str:
        return _ai_section(groq_client, groq_model, max_tok, system, prompt)

    # ── Tab 0: Overview ──────────────────────────────────────────────
    with tabs[0]:
        with st.spinner("Generating executive overview…"):
            overview = ai(
                BASE_SYSTEM,
                f"Write a thorough executive summary for {company} covering:\n"
                f"1. Market position and competitive standing\n"
                f"2. Key strengths (cite specific data points)\n"
                f"3. Main threats and weaknesses\n"
                f"4. Strategic recommendations (at least 2 specific actions)\n"
                f"5. Overall outlook\n\n"
                f"Complete all 5 sections fully. Data:\n\n{llm_context}",
            )
        st.markdown(overview)

        cb        = data.get("crunchbase", {})
        gh        = data.get("github", {})
        jobs_data = data.get("jobs", {})

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            price = yf_data.get("current_price")
            chg   = yf_data.get("price_change_30d_pct", 0)
            if yf_data.get("is_private"):
                st.metric("Stock Price", "Private co.")
            else:
                st.metric(
                    "Stock Price",
                    f"${price:.2f}" if price else "N/A",
                    delta=f"{chg:.1f}% (30d)" if price else None,
                )
        with m2:
            from scrapers.yahoo_finance import format_market_cap
            mc = yf_data.get("market_cap")
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
        cb_data  = data.get("crunchbase", {})
        sec_data = data.get("sec", {})

        fin_ctx = (
            f"Yahoo Finance: {json.dumps(yf_data, default=str)}\n"
            f"Company data (Wikipedia/Wikidata): {json.dumps(cb_data, default=str)}\n"
            f"SEC filings: {json.dumps(sec_data, default=str)}"
        )
        with st.spinner("Analysing financial data…"):
            fin = ai(
                BASE_SYSTEM,
                f"Write a complete financial analysis for {company} covering:\n"
                f"1. Valuation and market position\n"
                f"2. Revenue, growth trajectory, profitability\n"
                f"3. Financial risks and red flags\n"
                f"4. Investment outlook and recommendation\n"
                f"If data is unavailable (private company / rate limited), say so clearly "
                f"and use any available Wikipedia/Wikidata funding data instead.\n\n{fin_ctx}",
            )
        st.markdown(fin)

        price_hist = yf_data.get("price_history_30d", [])
        if price_hist:
            df = pd.DataFrame(price_hist).set_index("date")
            st.markdown("**📈 30-Day Stock Price**")
            st.line_chart(df["close"])

        filings = (sec_data.get("recent_10k") or []) + (sec_data.get("recent_10q") or [])
        if filings:
            st.markdown("**📋 Recent SEC Filings**")
            for f in filings[:6]:
                st.markdown(
                    f"- **{f['form']}** | {f.get('filing_date', '')} | "
                    f"[View filing]({f.get('url', '#')})"
                )

        overall_progress.progress(65)

    # ── Tab 2: News & Sentiment ──────────────────────────────────────
    with tabs[2]:
        news_d   = data.get("news", {})
        reddit_d = data.get("twitter", {})

        sent_ctx = (
            f"News articles: {json.dumps(news_d, default=str)}\n"
            f"Reddit discussions: {json.dumps(reddit_d, default=str)}"
        )
        with st.spinner("Analysing news and sentiment…"):
            sentiment = ai(
                BASE_SYSTEM,
                f"Write a complete news and sentiment analysis for {company} covering:\n"
                f"1. Overall news sentiment (positive/negative/neutral) with evidence\n"
                f"2. Key news themes and narratives from the last 30 days\n"
                f"3. Community/Reddit sentiment and main discussion topics\n"
                f"4. Reputation signals — any risks or PR issues?\n"
                f"5. What the sentiment means for competitive positioning\n\n{sent_ctx}",
            )
        st.markdown(sentiment)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**📰 Latest News Headlines**")
            for art in (news_d.get("articles") or [])[:8]:
                title = art.get("title", "")
                url   = art.get("url", "#")
                src   = art.get("source", "")
                pub   = (art.get("published_at") or "")[:16]
                st.markdown(f"- [{title}]({url})  \n  *{src} · {pub}*")
        with c2:
            st.markdown("**🗣️ Top Reddit Discussions**")
            for t in (reddit_d.get("top_tweets") or [])[:8]:
                text  = (t.get("text") or "")[:130]
                likes = t.get("likes", 0)
                sub   = t.get("subreddit", "")
                st.markdown(f"- {text}  \n  👍{likes} · r/{sub}" if sub else f"- {text} 👍{likes}")

        overall_progress.progress(72)

    # ── Tab 3: Tech & GitHub ─────────────────────────────────────────
    with tabs[3]:
        gh_d     = data.get("github", {})
        trends_d = data.get("trends", {})

        tech_ctx = (
            f"GitHub data: {json.dumps(gh_d, default=str)}\n"
            f"Google Trends: {json.dumps(trends_d, default=str)}"
        )
        with st.spinner("Analysing tech stack and developer trends…"):
            tech = ai(
                BASE_SYSTEM,
                f"Write a complete technical profile for {company} covering:\n"
                f"1. Primary tech stack and languages\n"
                f"2. Open-source strategy and developer community health\n"
                f"3. Search interest trend (rising/stable/declining) and what drives it\n"
                f"4. Developer mindshare vs competitors\n"
                f"5. Technical strengths and weaknesses\n\n{tech_ctx}",
            )
        st.markdown(tech)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🔧 Top GitHub Repositories**")
            for repo in (gh_d.get("top_repos") or [])[:6]:
                name  = repo.get("name", "")
                url   = repo.get("url", "#")
                stars = repo.get("stars", 0)
                lang  = repo.get("language", "N/A")
                desc  = (repo.get("description") or "")[:60]
                st.markdown(f"- [{name}]({url}) ⭐{stars:,} · {lang}  \n  *{desc}*")
        with c2:
            iot = trends_d.get("interest_over_time", [])
            if iot:
                df = pd.DataFrame(iot).set_index("date")
                st.markdown("**📊 Search Interest (Google Trends)**")
                st.area_chart(df["interest"])
            rising = trends_d.get("related_queries_rising", [])
            if rising:
                st.markdown("**🔺 Rising Searches**")
                st.markdown(", ".join(f"`{q}`" for q in rising[:8]))

        overall_progress.progress(80)

    # ── Tab 4: Products ──────────────────────────────────────────────
    with tabs[4]:
        ph_d = data.get("product_hunt", {})

        with st.spinner("Analysing product launches…"):
            products = ai(
                BASE_SYSTEM,
                f"Write a complete product analysis for {company} covering:\n"
                f"1. Product launch history and market reception\n"
                f"2. Most successful products and why they resonated\n"
                f"3. Product strategy and positioning patterns\n"
                f"4. Gaps or opportunities in their product portfolio\n"
                f"5. Competitive product positioning\n\n"
                f"Product Hunt data: {json.dumps(ph_d, default=str)}",
            )
        st.markdown(products)

        if ph_d.get("products"):
            st.markdown("**🚀 Product Hunt Launches**")
            for prod in ph_d["products"][:8]:
                if not prod.get("name"):
                    continue
                name    = prod.get("name", "")
                tagline = prod.get("tagline", "")
                votes   = prod.get("votes", 0)
                url     = prod.get("url", "")
                date    = (prod.get("launched_at") or "")[:16]
                line = f"- **{name}** — {tagline} | 👍 {votes}"
                if date:
                    line += f" · {date}"
                if url:
                    line += f" | [View]({url})"
                st.markdown(line)

        overall_progress.progress(87)

    # ── Tab 5: Hiring Intel ──────────────────────────────────────────
    with tabs[5]:
        jobs_d = data.get("jobs", {})
        ha     = jobs_d.get("hiring_analysis", {})

        with st.spinner("Analysing hiring trends…"):
            hiring = ai(
                BASE_SYSTEM,
                f"Write a complete hiring intelligence report for {company} covering:\n"
                f"1. Current hiring volume and growth phase\n"
                f"2. What role distribution (Eng/Sales/Marketing/Product) signals about strategy\n"
                f"3. Remote vs office hiring trends\n"
                f"4. Key departments they are doubling down on\n"
                f"5. What their hiring tells us about competitive moves in the next 6-12 months\n\n"
                f"Hiring data: {json.dumps(ha, default=str)}",
            )
        st.markdown(hiring)

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
            top_depts = ha.get("top_departments", [])
            if top_depts:
                st.markdown(
                    "**Top departments:** " +
                    " · ".join(f"{d[0]} ({d[1]})" for d in top_depts[:5])
                )

        overall_progress.progress(93)

    # ── Tab 6: SWOT ──────────────────────────────────────────────────
    with tabs[6]:
        with st.spinner("Generating SWOT analysis…"):
            swot = ai(
                BASE_SYSTEM,
                f"Write a thorough SWOT analysis for {company} using ALL the data below.\n\n"
                f"Format EXACTLY as:\n"
                f"## 💪 Strengths\n[at least 4 specific bullet points with data]\n\n"
                f"## ⚠️ Weaknesses\n[at least 4 specific bullet points with data]\n\n"
                f"## 🚀 Opportunities\n[at least 4 specific bullet points with data]\n\n"
                f"## 🔥 Threats\n[at least 4 specific bullet points with data]\n\n"
                f"## 🎯 Strategic Priorities\n[3 specific actionable recommendations]\n\n"
                f"Cite actual numbers, dates, and facts throughout. Complete all sections.\n\n"
                f"DATA:\n{llm_context}",
            )
        st.markdown(swot)
        overall_progress.progress(98)

    # ── Tab 7: Raw Data ──────────────────────────────────────────────
    with tabs[7]:
        st.markdown("### 📦 Raw Scraped Data")

        # Show error summary at top
        errors = {
            SOURCE_LABELS.get(k, k): v.get("error")
            for k, v in data.items() if v.get("error")
        }
        if errors:
            with st.expander("⚠️ Source warnings (click to expand)", expanded=False):
                for src, err in errors.items():
                    st.markdown(f"- **{src}**: {err}")

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
