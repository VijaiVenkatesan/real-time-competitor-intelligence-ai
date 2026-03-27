"""
AI Competitor Intelligence — Real-Time Enhanced
All API keys read from Streamlit Cloud secrets (never shown in UI).
9 free data sources: Yahoo Finance/Finnhub, Google News RSS, Google Trends,
GitHub, SEC Edgar, Product Hunt RSS, Wikipedia/Wikidata, Reddit, Job Boards

Groq free tier limits (per minute):
  llama-3.1-8b-instant  : ~30,000 TPM  ← default, safest choice
  llama-3.3-70b-versatile: ~6,000 TPM  ← hits limit easily with long prompts
Strategy: cap output tokens per call + add 2s delay between sequential LLM calls
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
    """Read secret from st.secrets (dict access) then os.environ fallback."""
    try:
        # st.secrets uses dict-style access, NOT .get()
        val = st.secrets[key]
        if val:
            return str(val).strip()
    except (KeyError, FileNotFoundError, Exception):
        pass
    return os.getenv(key, "").strip()


GROQ_API_KEY  = _get_secret("GROQ_API_KEY")
GITHUB_TOKEN  = _get_secret("GITHUB_TOKEN")
FINNHUB_KEY   = _get_secret("FINNHUB_API_KEY")

if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"]    = GROQ_API_KEY
if GITHUB_TOKEN:
    os.environ["GITHUB_TOKEN"]    = GITHUB_TOKEN
if FINNHUB_KEY:
    os.environ["FINNHUB_API_KEY"] = FINNHUB_KEY


# ─────────────────────────────────────────────────────────────────────
# GROQ MODEL CONFIG
# TPM limits for free tier (approx):
#   llama-3.1-8b-instant  → ~30,000 TPM  (safe for multiple calls)
#   llama-3.3-70b-versatile → ~6,000 TPM (need longer delays)
# ─────────────────────────────────────────────────────────────────────

GROQ_MODELS = {
    "llama-3.1-8b-instant":                          "Llama 3.1 8B ⚡ Fastest — recommended for free tier",
    "llama-3.3-70b-versatile":                        "Llama 3.3 70B 🧠 Best quality — slower on free tier",
    "meta-llama/llama-4-scout-17b-16e-instruct":      "Llama 4 Scout 17B 🦅 (preview)",
    "meta-llama/llama-4-maverick-17b-128e-instruct":  "Llama 4 Maverick 17B 🚀 (preview)",
    "qwen/qwen-3-32b":                                "Qwen 3 32B 🌏 (preview)",
}

# Safe output token caps per call that won't bust the free tier TPM
# 8B model: 30K TPM → can do 1500 out + ~500 prompt = 2000/call, 7 calls = 14K ✅
# 70B model: 6K TPM → must use 600 out max per call or add big delays
MODEL_SAFE_OUTPUT_TOKENS = {
    "llama-3.1-8b-instant":                          1500,
    "llama-3.3-70b-versatile":                        700,
    "meta-llama/llama-4-scout-17b-16e-instruct":      1200,
    "meta-llama/llama-4-maverick-17b-128e-instruct":  1200,
    "qwen/qwen-3-32b":                                1000,
}

# Delay in seconds between LLM calls to avoid burst rate limits
MODEL_INTER_CALL_DELAY = {
    "llama-3.1-8b-instant":                          1.5,
    "llama-3.3-70b-versatile":                        8.0,
    "meta-llama/llama-4-scout-17b-16e-instruct":      3.0,
    "meta-llama/llama-4-maverick-17b-128e-instruct":  3.0,
    "qwen/qwen-3-32b":                                3.0,
}


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _init_groq(api_key: str):
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        st.error("groq package not installed. Run: pip install groq")
        return None
    except Exception as e:
        st.error(f"Groq init error: {e}")
        return None


def _trim_context(context: str, max_chars: int = 6000) -> str:
    """Trim context to avoid sending huge prompts that eat into token budget."""
    if len(context) <= max_chars:
        return context
    return context[:max_chars] + "\n\n[...data trimmed to fit token limit...]"


def _ai_call(client, model: str, max_tokens: int, system: str, prompt: str) -> str:
    """Single Groq LLM call with error handling."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        err = str(e)
        if "decommissioned" in err or "model_decommissioned" in err:
            return (
                f"⚠️ **Model `{model}` decommissioned.** "
                "Select a different model in the sidebar."
            )
        if "rate_limit" in err.lower() or "429" in err or "too_many" in err.lower():
            return (
                "⚠️ **Groq rate limit hit.**\n\n"
                "**Fix:** Switch to **Llama 3.1 8B** in the sidebar (highest free-tier TPM). "
                "Then wait 60 seconds and re-run."
            )
        if "context_length" in err.lower() or "too large" in err.lower():
            return "⚠️ Prompt too long — context was trimmed but still exceeded limit. Try Quick depth."
        return f"⚠️ AI error: {err}"


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
        use_yahoo   = st.checkbox("📈 Financials",     value=True)
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
        index=0,   # default: llama-3.1-8b-instant — safest for free tier
    )

    safe_tokens = MODEL_SAFE_OUTPUT_TOKENS[groq_model]
    delay_s     = MODEL_INTER_CALL_DELAY[groq_model]

    st.caption(
        f"📝 {safe_tokens} tokens/section · {delay_s}s between calls\n\n"
        f"⏱️ Est. analysis time: ~{int(7 * delay_s + 30)}s"
    )

    if groq_model == "llama-3.3-70b-versatile":
        st.warning(
            "⚠️ 70B model has a low free-tier TPM (6K/min). "
            "Analysis will take ~60s with forced delays. "
            "Switch to **Llama 3.1 8B** for faster results."
        )

    st.markdown("---")
    st.caption("🔒 Keys stored in Streamlit Cloud secrets only.")


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

if FINNHUB_KEY:
    st.caption("✅ Finnhub API connected — global stock data enabled (US, India NSE/BSE, UK, EU, Asia)")
else:
    st.info(
        "💡 **Optional:** Add `FINNHUB_API_KEY` to Streamlit secrets for reliable global stock data. "
        "Free key at [finnhub.io/register](https://finnhub.io/register) — no credit card needed."
    )

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
    "yahoo_finance": "📈 Financials",
    "news":          "📰 Google News",
    "trends":        "📊 Trends",
    "github":        "💻 GitHub",
    "sec":           "📋 SEC Edgar",
    "product_hunt":  "🚀 Product Hunt",
    "crunchbase":    "🏢 Wikipedia",
    "twitter":       "🗣️ Reddit",
    "jobs":          "👔 Jobs",
}

main_tab, about_tab = st.tabs(["🔍 Analyse", "ℹ️ About & Tools"])

# ── ABOUT TAB ────────────────────────────────────────────────────────
with about_tab:
    st.markdown("## 🔍 AI Real Time Competitor Intelligence")
    st.markdown(
        "Autonomous market research powered by **9 real-time free data sources** "
        "and AI synthesis via Groq. Enter any company name and get a full "
        "competitive intelligence report in under 2 minutes — no paid APIs required."
    )

    st.markdown("---")

    # ── How It Works ────────────────────────────────────────────────
    st.markdown("### ⚙️ How It Works")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
**1️⃣ Data Collection**
All 9 scrapers run in parallel using Python's `ThreadPoolExecutor`.
Typical collection time: **5–15 seconds**.
Each source has independent error handling — one failure never blocks the rest.
        """)
    with col2:
        st.markdown("""
**2️⃣ Context Building**
Raw JSON from all sources is converted into a structured markdown summary.
Long payloads are trimmed to fit within LLM context windows without losing key facts.
        """)
    with col3:
        st.markdown("""
**3️⃣ AI Synthesis**
Groq (Llama 3.1 8B) analyses each section sequentially with a **1.5s delay** between calls to respect free-tier rate limits (30K TPM).
Total AI time: **~20–30 seconds**.
        """)

    st.markdown("---")

    # ── Data Sources ────────────────────────────────────────────────
    st.markdown("### 📡 Data Sources")

    sources = [
        {
            "icon": "📈", "name": "Financial Data",
            "provider": "Finnhub API (primary) · yfinance (fallback)",
            "what": "Stock price, market cap, P/E ratio, 52-week high/low, revenue, profit margin, employee count, sector",
            "free": "✅ Free", "key": "Optional: `FINNHUB_API_KEY`",
            "freq": "Real-time", "works_for": "Public companies (NYSE/NASDAQ/LSE etc.)",
            "note": "Private companies (Stripe, OpenAI etc.) are auto-detected and skipped gracefully.",
            "link": "https://finnhub.io/register",
        },
        {
            "icon": "📰", "name": "Google News RSS",
            "provider": "news.google.com/rss",
            "what": "Latest news articles from all major sources, publication dates, keyword-based sentiment scoring (positive/negative/neutral)",
            "free": "✅ Free", "key": "None required",
            "freq": "Continuous", "works_for": "Any company globally",
            "note": "Uses Python's built-in `xml.etree` — no external library needed.",
            "link": "https://news.google.com",
        },
        {
            "icon": "📊", "name": "Google Trends",
            "provider": "pytrends (unofficial wrapper)",
            "what": "Search interest score (0–100) over 3 months, trend direction (Rising/Stable/Declining), top rising queries related to the company",
            "free": "✅ Free", "key": "None required",
            "freq": "Daily",    "works_for": "Any searchable term globally",
            "note": "Google rate-limits this on shared IPs. May occasionally return an error — retry after 30s.",
            "link": "https://trends.google.com",
        },
        {
            "icon": "💻", "name": "GitHub API",
            "provider": "GitHub REST API v3",
            "what": "Organisation repos, stars, forks, primary languages, recent commit activity, open-source presence rating",
            "free": "✅ Free", "key": "Optional: `GITHUB_TOKEN` (raises limit 60→5000 req/hr)",
            "freq": "Real-time", "works_for": "Companies with a GitHub org",
            "note": "Works without a token for most companies. Add token if you hit rate limits.",
            "link": "https://github.com/settings/tokens",
        },
        {
            "icon": "📋", "name": "SEC Edgar",
            "provider": "SEC EDGAR Submissions API (US Government)",
            "what": "Recent 10-K (annual) and 10-Q (quarterly) filings with direct links to official documents",
            "free": "✅ Free", "key": "None required — public government API",
            "freq": "Real-time", "works_for": "Public US companies only",
            "note": "Non-US listed companies (e.g. Indian, European) will show N/A — they file with different regulators.",
            "link": "https://efts.sec.gov",
        },
        {
            "icon": "🚀", "name": "Product Hunt",
            "provider": "Product Hunt public RSS feed",
            "what": "Product launches, upvote counts, taglines, launch dates, community traction",
            "free": "✅ Free", "key": "None required",
            "freq": "Continuous", "works_for": "Consumer/SaaS products listed on Product Hunt",
            "note": "RSS feed filters by company name mention. B2B/enterprise companies may have fewer listings.",
            "link": "https://www.producthunt.com/feed",
        },
        {
            "icon": "🏢", "name": "Wikipedia + Wikidata + OpenCorporates",
            "provider": "Wikipedia REST API · Wikidata SPARQL · OpenCorporates API",
            "what": "Company description, founded year, headquarters, employee count, funding mentions, registered company number, jurisdiction",
            "free": "✅ Free", "key": "None required",
            "freq": "Continuous", "works_for": "Any company with a Wikipedia page or company registration",
            "note": "Replaces Crunchbase (which blocks scraping). Data depth varies — well-known companies have richer entries.",
            "link": "https://www.wikidata.org",
        },
        {
            "icon": "🗣️", "name": "Reddit",
            "provider": "Reddit public JSON search API",
            "what": "Community mentions across r/investing, r/technology, r/startups and more. Post scores, comment counts, sentiment analysis, subreddit breakdown",
            "free": "✅ Free", "key": "None required — public JSON API",
            "freq": "Real-time", "works_for": "Any company discussed on Reddit",
            "note": "Replaces Twitter/X (API now costs $100+/mo). Reddit discussions are often more analytical and in-depth.",
            "link": "https://www.reddit.com/search.json",
        },
        {
            "icon": "👔", "name": "Job Boards",
            "provider": "Greenhouse API · Lever API",
            "what": "Open job listings, department breakdown (Eng/Sales/Marketing/Product), location analysis, remote roles count, inferred growth phase",
            "free": "✅ Free", "key": "None required — public ATS APIs",
            "freq": "Daily", "works_for": "Companies using Greenhouse or Lever ATS",
            "note": "Companies on Workday, iCIMS, or custom career pages will show N/A. Covers ~40% of tech startups.",
            "link": "https://boards-api.greenhouse.io",
        },
    ]

    for src in sources:
        with st.expander(f"{src['icon']} **{src['name']}** — {src['provider']}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**What it provides:** {src['what']}")
                st.markdown(f"**Works for:** {src['works_for']}")
                st.markdown(f"**ℹ️ Note:** {src['note']}")
            with c2:
                st.markdown(f"**Cost:** {src['free']}")
                st.markdown(f"**API Key:** {src['key']}")
                st.markdown(f"**Update frequency:** {src['freq']}")
                st.markdown(f"[🔗 Learn more]({src['link']})")

    st.markdown("---")

    # ── AI Engine ───────────────────────────────────────────────────
    st.markdown("### 🤖 AI Engine — Groq")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Why Groq?**
- Fastest LLM inference available (uses custom LPU hardware)
- Free tier: no credit card, generous token limits
- Llama 3.1 8B: **~30,000 tokens/minute** on free tier — enough for 7 analysis sections
- All models are open-source (Meta Llama, Qwen)

**Free tier limits:**
| Model | TPM | Best for |
|-------|-----|----------|
| Llama 3.1 8B | ~30K | ⚡ Default — fast & reliable |
| Llama 3.3 70B | ~6K | 🧠 Higher quality, slower |
| Llama 4 Scout | ~12K | 🦅 Preview — may change |
        """)
    with col2:
        st.markdown("""
**Rate limit strategy:**
Each analysis section is called sequentially (not in parallel) with a **1.5s enforced delay** between calls for the 8B model.

This keeps total token usage well within the 30K/min window even for large companies.

**Token budget per section:**
- Quick: 1,200 tokens
- Standard: 1,500 tokens
- Deep: 2,000 tokens

Get your free API key → [console.groq.com](https://console.groq.com)
        """)

    st.markdown("---")

    # ── Analysis Output Tabs ────────────────────────────────────────
    st.markdown("### 📊 What Each Analysis Tab Contains")
    tab_info = [
        ("📊 Overview",        "5-bullet executive summary · Key metrics (stock price, market cap, GitHub stars, open roles)"),
        ("💰 Financials",      "Stock analysis · Revenue & profitability · SEC filing links · 30-day price chart"),
        ("📰 News & Sentiment","News headlines with links · Reddit discussion highlights · Sentiment score breakdown"),
        ("💻 Tech & GitHub",   "Tech stack & languages · Top repos with stars · Search interest chart · Rising queries"),
        ("🚀 Products",        "Product Hunt launch history · Upvote counts · Product strategy analysis"),
        ("👔 Hiring Intel",    "Role breakdown by function · Growth phase inference · Remote vs office ratio"),
        ("⚔️ SWOT",            "Strengths / Weaknesses / Opportunities / Threats · Top 3 strategic recommendations"),
        ("📋 Raw Data",        "Full JSON output per source · Error log · One-click JSON download"),
    ]
    for tab_name, tab_desc in tab_info:
        st.markdown(f"- **{tab_name}** — {tab_desc}")

    st.markdown("---")

    # ── Setup Guide ─────────────────────────────────────────────────
    st.markdown("### 🚀 Setup Guide")
    st.markdown("""
**Required (1 step):**
```toml
# Streamlit Cloud → your app → ⋮ → Settings → Secrets
GROQ_API_KEY = "gsk_your_key_here"
```
Get free key at [console.groq.com](https://console.groq.com)

**Optional (better financial data):**
```toml
FINNHUB_API_KEY = "your_key_here"   # finnhub.io/register — free, no credit card
GITHUB_TOKEN    = "ghp_your_token"  # github.com/settings/tokens — raises API limit
```

**Best companies to analyse:**
- ✅ Public US tech: `Shopify`, `Cloudflare`, `Datadog`, `Snowflake`
- ✅ AI companies: `OpenAI`, `Anthropic`, `Hugging Face`, `Mistral`
- ✅ SaaS: `Notion`, `Figma`, `Linear`, `Vercel`, `Supabase`
- ⚠️ Non-US listed (SEC Edgar will show N/A, all other sources work fine)
- ❌ Very small/obscure companies may have limited data across all sources
    """)

    st.markdown("---")

    # ── Tech Stack ──────────────────────────────────────────────────
    st.markdown("### 🛠️ Tech Stack")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
**Backend**
- Python 3.11
- `requests` — HTTP scraping
- `yfinance` / `finnhub-python`
- `pytrends` — Google Trends
- `concurrent.futures` — parallel scraping
        """)
    with c2:
        st.markdown("""
**AI / LLM**
- `groq` — LLM client
- `langchain` — agent framework
- Llama 3.1 8B (default)
- Sequential calls + rate-limit delays
        """)
    with c3:
        st.markdown("""
**Frontend**
- `streamlit` — UI & deployment
- `pandas` — data processing
- Streamlit Cloud — hosting
- GitHub — source control
        """)

    st.markdown("---")
    st.markdown(
        "**Built with ❤️ using 100% open-source, zero-cost tools** · "
        "[GitHub Repo](https://github.com/VijaiVenkatesan/competitor-intelligence-ai)"
    )

# ── ANALYSE TAB ──────────────────────────────────────────────────────
with main_tab:
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
        st.markdown("### 📡 Data Sources — all free, no keys required")
        cards = [
            ("📈 Financials",        "Stock price, market cap via Finnhub",   "Real-time"),
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
        for i, (name, desc, freq) in enumerate(cards):
            with cols[i % 3]:
                st.markdown(
                    f'<div class="metric-card"><b>{name}</b><br>'
                    f'<small>{desc}</small><br>'
                    f'<small>🕒 {freq} &nbsp;·&nbsp; 🟢 Free</small></div>',
                    unsafe_allow_html=True,
                )
        st.stop()

    # ── RUN ANALYSIS (inside main_tab) ──────────────────────────────

    if run_btn and company:

        groq_client = _init_groq(GROQ_API_KEY)
        if not groq_client:
            st.stop()

        BASE_SYSTEM = (
            "You are an expert competitive intelligence analyst. "
            "Analyse the provided real-time data concisely but completely. "
            "Use bullet points and bold text. "
            "Always finish every sentence — never stop mid-thought. "
            "Ground all claims in the data provided."
        )

        st.markdown(f"## 🔎 Analysing: **{company}**")
        overall_progress = st.progress(0, text="Starting data collection…")
        status_box = st.empty()

        # ── Step 1: Data collection (parallel) ──────────────────────────
        status_box.info(f"📡 Collecting from {len(enabled_sources)} sources in parallel…")
        t_start = time.time()

        from agents.realtime_agent import run_all_realtime_scrapers, build_llm_context
        raw_data    = run_all_realtime_scrapers(company, enabled_sources=enabled_sources)
        llm_context = _trim_context(build_llm_context(raw_data), max_chars=5000)
        data        = raw_data.get("data", {})

        elapsed = round(time.time() - t_start, 1)
        overall_progress.progress(30, text=f"✅ Data collected in {elapsed}s — running AI analysis…")

        # Source badges
        badge_html = ""
        for key, label in SOURCE_LABELS.items():
            if key not in data:
                continue
            has_err = bool(data[key].get("error"))
            css  = "warn" if has_err else ""
            icon = "⚠️"  if has_err else "✅"
            badge_html += f'<span class="source-badge {css}">{label} {icon}</span>'
        st.markdown(badge_html, unsafe_allow_html=True)

        yf_data = data.get("yahoo_finance", {})
        if yf_data.get("error") and not yf_data.get("is_private"):
            if FINNHUB_KEY:
                st.info(
                    f"ℹ️ **Financial data limited for '{company}'.** "
                    "Finnhub free tier has limited coverage for Indian (NSE/BSE) and some non-US stocks. "
                    "The analysis uses Wikipedia/Wikidata funding data instead. "
                    f"*Details: {yf_data.get('error', '')[:120]}*"
                )
            else:
                st.warning(
                    "💡 **Stock data unavailable** — no `FINNHUB_API_KEY` in secrets. "
                    "Add a free key from [finnhub.io/register](https://finnhub.io/register) "
                    "for reliable global stock data."
                )

        tabs = st.tabs([
            "📊 Overview", "💰 Financials", "📰 News & Sentiment",
            "💻 Tech & GitHub", "🚀 Products", "👔 Hiring Intel",
            "⚔️ SWOT", "📋 Raw Data",
        ])

        # ── Helper: call AI with automatic delay ────────────────────────
        _last_call_time = [0.0]

        def ai(prompt: str, context: str = "", section_label: str = "") -> str:
            """Rate-limit-safe Groq call: enforces delay since last call."""
            elapsed_since_last = time.time() - _last_call_time[0]
            needed_delay = MODEL_INTER_CALL_DELAY[groq_model] - elapsed_since_last
            if needed_delay > 0:
                time.sleep(needed_delay)

            full_prompt = f"{prompt}\n\nDATA:\n{_trim_context(context, 3500)}" if context else prompt
            result = _ai_call(
                groq_client, groq_model,
                MODEL_SAFE_OUTPUT_TOKENS[groq_model],
                BASE_SYSTEM, full_prompt,
            )
            _last_call_time[0] = time.time()
            return result

        # ── Tab 0: Overview ──────────────────────────────────────────────
        with tabs[0]:
            with st.spinner("Generating overview…"):
                st.markdown(ai(
                    f"Write a 5-bullet executive summary of {company}: market position, "
                    f"key strengths (with data), main threats, and 2 strategic recommendations.",
                    llm_context,
                ))
            overall_progress.progress(42)

            cb        = data.get("crunchbase", {})
            gh        = data.get("github", {})
            jobs_data = data.get("jobs", {})

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                price = yf_data.get("current_price")
                # Safely resolve change — both keys may be None; cast to float only when set
                _chg_raw = yf_data.get("price_change_30d_pct") or yf_data.get("price_change_pct")
                chg = float(_chg_raw) if _chg_raw is not None else None
                if yf_data.get("is_private"):
                    st.metric("Stock Price", "Private co.")
                else:
                    st.metric(
                        "Stock Price",
                        f"${price:.2f}" if price else "N/A",
                        delta=f"{chg:.1f}% (30d)" if (price and chg is not None) else None,
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
                roles = jobs_data.get("hiring_analysis", {}).get("total_open_roles", 0)
                st.metric("Open Roles", roles or "N/A")

        # ── Tab 1: Financials ────────────────────────────────────────────
        with tabs[1]:
            sec_data = data.get("sec", {})
            fin_ctx  = (
                f"Stock/Financial: {json.dumps(yf_data, default=str)[:2000]}\n"
                f"Company info: {json.dumps(data.get('crunchbase', {}), default=str)[:1000]}\n"
                f"SEC: {json.dumps(sec_data, default=str)[:500]}"
            )
            with st.spinner("Analysing financials…"):
                st.markdown(ai(
                    f"Analyse {company}'s finances: valuation, revenue growth, profitability, "
                    f"risks, and investment outlook. If private, use available funding data.",
                    fin_ctx,
                ))
            overall_progress.progress(54)

            if yf_data.get("price_history_30d"):
                df = pd.DataFrame(yf_data["price_history_30d"]).set_index("date")
                st.markdown("**📈 30-Day Stock Price**")
                st.line_chart(df["close"])

            filings = (sec_data.get("recent_10k") or []) + (sec_data.get("recent_10q") or [])
            if filings:
                st.markdown("**📋 SEC Filings**")
                for f in filings[:5]:
                    st.markdown(f"- **{f['form']}** | {f.get('filing_date','')} | [View]({f.get('url','#')})")

        # ── Tab 2: News & Sentiment ──────────────────────────────────────
        with tabs[2]:
            news_d   = data.get("news", {})
            reddit_d = data.get("twitter", {})
            sent_ctx = (
                f"News: {json.dumps((news_d.get('articles') or [])[:8], default=str)[:2000]}\n"
                f"Sentiment: {json.dumps(news_d.get('sentiment_summary'), default=str)}\n"
                f"Reddit: {json.dumps((reddit_d.get('top_tweets') or [])[:5], default=str)[:1000]}"
            )
            with st.spinner("Analysing news & sentiment…"):
                st.markdown(ai(
                    f"Analyse {company}'s news coverage and community sentiment: "
                    f"overall tone, key themes, reputation signals, and competitive implications.",
                    sent_ctx,
                ))
            overall_progress.progress(64)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**📰 Latest News**")
                for art in (news_d.get("articles") or [])[:7]:
                    t = art.get("title", ""); u = art.get("url", "#"); s = art.get("source", "")
                    st.markdown(f"- [{t}]({u}) *{s}*")
            with c2:
                st.markdown("**🗣️ Reddit Discussions**")
                for t in (reddit_d.get("top_tweets") or [])[:7]:
                    text  = (t.get("text") or "")[:110]
                    likes = t.get("likes", 0)
                    st.markdown(f"- {text} 👍{likes}")

        # ── Tab 3: Tech & GitHub ─────────────────────────────────────────
        with tabs[3]:
            gh_d     = data.get("github", {})
            trends_d = data.get("trends", {})
            tech_ctx = (
                f"GitHub: org={gh_d.get('org_handle')}, stars={gh_d.get('total_stars')}, "
                f"languages={gh_d.get('top_languages')}, repos={json.dumps((gh_d.get('top_repos') or [])[:3], default=str)[:500]}\n"
                f"Trends: direction={trends_d.get('trend_direction')}, "
                f"avg={trends_d.get('average_interest')}, rising={trends_d.get('related_queries_rising', [])[:5]}"
            )
            with st.spinner("Analysing tech profile…"):
                st.markdown(ai(
                    f"Analyse {company}'s tech stack, open-source presence, "
                    f"developer mindshare, and search trend trajectory.",
                    tech_ctx,
                ))
            overall_progress.progress(74)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**🔧 Top Repos**")
                for r in (gh_d.get("top_repos") or [])[:5]:
                    st.markdown(f"- [{r.get('name','')}]({r.get('url','#')}) ⭐{r.get('stars',0):,} · {r.get('language','N/A')}")
            with c2:
                iot = trends_d.get("interest_over_time", [])
                if iot:
                    df = pd.DataFrame(iot).set_index("date")
                    st.markdown("**📊 Search Interest**")
                    st.area_chart(df["interest"])

        # ── Tab 4: Products ──────────────────────────────────────────────
        with tabs[4]:
            ph_d = data.get("product_hunt", {})
            ph_ctx = (
                f"Products: {json.dumps((ph_d.get('products') or [])[:5], default=str)[:1500]}\n"
                f"Total upvotes: {ph_d.get('total_upvotes', 0)}"
            )
            with st.spinner("Analysing products…"):
                st.markdown(ai(
                    f"Analyse {company}'s product launch history and market reception. "
                    f"What does it reveal about their product strategy?",
                    ph_ctx,
                ))
            overall_progress.progress(82)

            st.markdown("**🚀 Product Hunt Launches**")
            for prod in (ph_d.get("products") or [])[:8]:
                if not prod.get("name"):
                    continue
                line = f"- **{prod['name']}** — {prod.get('tagline','')} | 👍 {prod.get('votes',0)}"
                if prod.get("url"):
                    line += f" | [View]({prod['url']})"
                st.markdown(line)

        # ── Tab 5: Hiring Intel ──────────────────────────────────────────
        with tabs[5]:
            ha = data.get("jobs", {}).get("hiring_analysis", {})
            with st.spinner("Analysing hiring…"):
                st.markdown(ai(
                    f"Analyse {company}'s hiring: role distribution, growth phase, "
                    f"strategic signals from open positions.",
                    json.dumps(ha, default=str)[:1500],
                ))
            overall_progress.progress(89)

            if ha:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("🔧 Engineering", ha.get("engineering_roles", 0))
                c2.metric("💼 Sales",       ha.get("sales_roles", 0))
                c3.metric("📣 Marketing",   ha.get("marketing_roles", 0))
                c4.metric("🎯 Product",     ha.get("product_roles", 0))
                if ha.get("inferred_growth_phase"):
                    st.info(f"**Growth phase:** {ha['inferred_growth_phase']}")

        # ── Tab 6: SWOT ──────────────────────────────────────────────────
        with tabs[6]:
            with st.spinner("Generating SWOT…"):
                st.markdown(ai(
                    f"Write a complete SWOT analysis for {company}.\n"
                    f"## 💪 Strengths\n## ⚠️ Weaknesses\n"
                    f"## 🚀 Opportunities\n## 🔥 Threats\n"
                    f"## 🎯 Top 3 Strategic Recommendations\n"
                    f"Use 3-4 bullets per section. Cite specific data.",
                    llm_context,
                ))
            overall_progress.progress(97)

        # ── Tab 7: Raw Data ──────────────────────────────────────────────
        with tabs[7]:
            st.markdown("### 📦 Raw Data")
            errors = {SOURCE_LABELS.get(k, k): v.get("error") for k, v in data.items() if v.get("error")}
            if errors:
                with st.expander("⚠️ Source warnings"):
                    for src, err in errors.items():
                        st.markdown(f"- **{src}**: {err}")

            for key, val in data.items():
                with st.expander(f"{SOURCE_LABELS.get(key, key)} — raw JSON"):
                    st.json(val)

            st.download_button(
                "⬇️ Download Full Report (JSON)",
                data=json.dumps(raw_data, default=str, indent=2),
                file_name=f"{company.lower().replace(' ','_')}_intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

        overall_progress.progress(100, text="✅ Analysis complete!")
        status_box.success(
            f"✅ **{company}** analysed across **{len(data)} sources** in "
            f"{round(time.time() - t_start, 1)}s"
        )
