# 🔍 AI Real Time Competitor Intelligence

> Autonomous market research powered by **9 real-time free data sources** + AI synthesis
> Supports **Indian (NSE/BSE) and global companies** — 100% free, zero paid APIs required

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Click%20Here-red?style=for-the-badge)](https://real-time-competitor-intelligence-ai.streamlit.app)

**[🚀 Try It Live →](https://real-time-competitor-intelligence-ai.streamlit.app)**

---

## ✨ What It Does

Enter any company name — Indian or global — and get a full competitive intelligence report in **under 30 seconds**. All 9 data sources run in parallel, results are synthesised by AI into 8 structured analysis tabs.

---

## 📡 Data Sources — All Free, No Keys Required

| Source | What It Provides | Provider | Key Needed |
|--------|-----------------|----------|-----------|
| 📈 **Financial Data** | Stock price, market cap, P/E, 52W high/low, revenue, margins | yfinance (NSE/BSE .NS/.BO) + Finnhub | ❌ None (Finnhub optional) |
| 📰 **Google News RSS** | Latest articles + keyword sentiment scoring | news.google.com/rss | ❌ None |
| 📊 **Google Trends** | Search interest (0–100), trend direction, rising queries | pytrends | ❌ None |
| 💻 **GitHub API** | Tech stack, stars, repos, commit activity | GitHub REST API v3 | ❌ None (token optional) |
| 📋 **SEC Edgar** | 10-K / 10-Q filings with direct links | US Gov EDGAR API | ❌ None |
| 🚀 **Product Hunt** | Product launches, upvotes, community traction | Public RSS feed | ❌ None |
| 🏢 **Wikipedia + Wikidata** | Founded year, HQ, description, funding mentions | Wikipedia REST + Wikidata SPARQL | ❌ None |
| 🗣️ **Reddit** | Community mentions, sentiment, top discussions | Reddit public JSON API | ❌ None |
| 👔 **Job Boards** | Open roles, dept breakdown, hiring growth phase | Greenhouse + Lever public APIs | ❌ None |

> **Only 1 secret needed:** `GROQ_API_KEY` to power AI synthesis. Everything else is zero-config.

---

## 🌍 Global + Indian Company Coverage

### Indian Companies (NSE/BSE) — 200+ pre-mapped

| Category | Companies Supported |
|----------|-------------------|
| **IT Services** | TCS, Infosys, Wipro, HCL Tech, Tech Mahindra, LTIMindtree, Mphasis, Persistent, Coforge, Hexaware, Cyient, Zensar, KPIT, Birlasoft, Mastek, Oracle Financial (OFSS), Tata Elxsi |
| **Telecom** | Jio Financial (JIOFIN), Bharti Airtel, Vodafone Idea |
| **Finance** | HDFC Bank, ICICI Bank, SBI, Bajaj Finance, Axis Bank, Kotak, IndusInd, Angel One |
| **Consumer** | Reliance, Tata Motors, Maruti, Asian Paints, ITC, HUL, Nestle, Dabur, Britannia |
| **New-age** | Zomato, Nykaa, Paytm, Delhivery, Ola Electric, Indiamart, Info Edge (Naukri) |
| **Pharma** | Sun Pharma, Dr Reddy's, Cipla, Lupin, Biocon, Torrent Pharma, Alkem |
| **PSU** | HAL, BEL, IRFC, RVNL, NMDC, SAIL, GAIL, NTPC, ONGC, Coal India |

### Private Indian Companies (auto-detected, no stock lookup)
Swiggy, Zepto, Razorpay, CRED, Dream11, Byju's, Unacademy, PhysicsWallah, Lenskart → Financial data sourced from Wikipedia/Wikidata instead.

### Global Coverage
US (NYSE/NASDAQ), UK (LSE), EU, Singapore, Japan, South Korea, Taiwan, China

---

## 🖥️ Analysis Tabs

| Tab | Contents |
|-----|---------|
| 📊 **Overview** | 5-bullet executive summary · Stock price · Market cap · GitHub stars · Open roles |
| 💰 **Financials** | AI analysis · 30-day price chart · Revenue & margins · SEC filing links |
| 📰 **News & Sentiment** | Google News headlines · Reddit top posts · Sentiment breakdown |
| 💻 **Tech & GitHub** | Tech stack · Top repos · Google Trends chart · Rising searches |
| 🚀 **Products** | Product Hunt history · Upvotes · Product strategy analysis |
| 👔 **Hiring Intel** | Role breakdown · Growth phase inference · Remote ratio |
| ⚔️ **SWOT** | Strengths · Weaknesses · Opportunities · Threats · 3 strategic recommendations |
| 📋 **Raw Data** | Full JSON per source · Error log · One-click download |

---

## 🚀 Setup (2 minutes)

### Deploy to Streamlit Cloud

```bash
# 1. Fork this repo on GitHub

# 2. Go to share.streamlit.io → New app → connect your fork

# 3. Settings → Secrets → add:
GROQ_API_KEY = "gsk_your_key_here"

# Optional for better US stock data:
FINNHUB_API_KEY = "your_key"    # free at finnhub.io/register
GITHUB_TOKEN = "ghp_your_token" # github.com/settings/tokens

# 4. Deploy!
```

### Run Locally

```bash
git clone https://github.com/VijaiVenkatesan/competitor-intelligence-ai
cd competitor-intelligence-ai
pip install -r requirements.txt

# Create .env file
echo 'GROQ_API_KEY=gsk_your_key_here' > .env

streamlit run app.py
```

Get a free Groq key at [console.groq.com](https://console.groq.com) — no credit card needed.

---

## 📁 Project Structure

```
competitor-intelligence-ai/
│
├── app.py                          ← Streamlit UI (Analyse + About & Tools tabs)
├── requirements.txt                ← All dependencies
├── .env.example                    ← Secrets template
│
├── agents/
│   ├── __init__.py
│   └── realtime_agent.py           ← Parallel scraper orchestrator + LLM context builder
│
└── scrapers/
    ├── __init__.py
    ├── yahoo_finance.py            ← Financial data: NSE → yfinance .NS → Finnhub chain
    ├── newsapi_scraper.py          ← Google News RSS (replaces NewsAPI)
    ├── google_trends.py            ← pytrends with urllib3 2.0 patch + retry on 429
    ├── github_scraper.py           ← GitHub REST API v3
    ├── sec_edgar.py                ← SEC EDGAR Submissions API
    ├── product_hunt.py             ← Product Hunt RSS feed
    ├── crunchbase_scraper.py       ← Wikipedia + Wikidata + OpenCorporates
    ├── twitter_scraper.py          ← Reddit public JSON API (replaces Twitter/X)
    └── job_boards.py               ← Greenhouse + Lever public APIs
```

---

## ⚙️ How It Works

```
  You type a company name
          │
          ▼
  ┌─────────────────────────────────────────────┐
  │  9 scrapers run in parallel (6 threads)     │
  │  Timeout: 60s total, each source independent│
  └─────────────────────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────────────────────┐
  │  Context builder: raw JSON → structured     │
  │  markdown, trimmed to ~3,500 chars/section  │
  └─────────────────────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────────────────────┐
  │  Groq AI: 7 sequential calls                │
  │  1.5s enforced delay between calls          │
  │  Stays within 30K TPM free-tier limit       │
  └─────────────────────────────────────────────┘
          │
          ▼
  8-tab Streamlit dashboard + JSON export
```

---

## 🤖 AI Models (Groq Free Tier)

| Model | TPM Limit | Delay | Best For |
|-------|-----------|-------|---------|
| `llama-3.1-8b-instant` | ~30K | 1.5s | ⚡ **Default** — fast, reliable |
| `llama-3.3-70b-versatile` | ~6K | 8s | 🧠 Higher quality, slower |
| `llama-4-scout-17b` | ~12K | 3s | 🦅 Preview |
| `llama-4-maverick-17b` | ~12K | 3s | 🚀 Preview |
| `qwen-3-32b` | ~10K | 3s | 🌏 Preview |

> ❌ Removed (decommissioned by Groq): `llama-3.1-70b-versatile`, `mixtral-8x7b-32768`

---

## 🌐 Expected Behaviour by Company Type

| Company Type | Financials | SEC | Jobs | Reddit | Notes |
|-------------|-----------|-----|------|--------|-------|
| Indian listed (NSE) | ✅ INR | ⚠️ | ⚠️ | ⚠️ | SEC/Jobs/Reddit expected ⚠️ |
| Indian private | ⚠️ Wikipedia | ⚠️ | ⚠️ | ⚠️ | Funding from Wikipedia |
| US public | ✅ USD | ✅ | ✅ | ✅ | Full data |
| US private | ⚠️ Wikipedia | ⚠️ | ✅ | ✅ | No stock data |
| EU/UK public | ✅ local | ⚠️ | varies | varies | No SEC filing |

**⚠️ = expected, not broken.** AI analysis uses whichever sources return data.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **UI & Hosting** | Streamlit 1.55+, Streamlit Cloud |
| **AI / LLM** | Groq API, Llama 3.1 8B, langchain, langchain-groq |
| **Financial Data** | yfinance (NSE .NS / BSE .BO), finnhub-python |
| **Web Scraping** | requests, beautifulsoup4, trafilatura |
| **Trends** | pytrends (with urllib3 2.0 compatibility patch) |
| **Parallelism** | concurrent.futures.ThreadPoolExecutor |
| **Data** | pandas, numpy |

---

## ⚠️ Known Limitations

| Issue | Cause | Workaround |
|-------|-------|-----------|
| Finnhub 403 for Indian stocks | Free tier has limited NSE coverage | yfinance .NS works as automatic fallback |
| Google Trends 429 | Shared Streamlit Cloud IP rate-limited | Auto-retry 3× with backoff; re-run after 2 min |
| NSE direct API blocked | NSE blocks server-side requests | yfinance .NS suffix is the reliable path |
| Jobs ⚠️ for Indian companies | TCS/Infosys use own career portals | Expected; try Shopify/HubSpot for job data |
| SEC ⚠️ for non-US | Indian/EU companies don't file with SEC | Expected; SEBI filings not yet supported |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-source`)
3. Commit your changes
4. Open a pull request

Ideas welcome: new data sources, SEBI filing support, export to PDF/Excel, comparison mode for multiple companies.

---

## 📄 License

MIT License — free for personal and commercial use.

---

**Built with ❤️ using 100% open-source, zero-cost tools**

⭐ Star this repo if you find it useful!
