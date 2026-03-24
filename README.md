# 🔍 AI Competitor Intelligence

> Autonomous market research powered by **9 real-time data sources** + AI synthesis — **100% free, zero API keys required**

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**[🚀 Try It Live →](https://competitor-intelligence-ai.streamlit.app/)**

---

## ✨ What It Does

Enter any company name and get a comprehensive intelligence report in under 2 minutes — pulling live data from 9 sources simultaneously, then synthesising it with AI into actionable insights across 7 analysis tabs.

---

## 📡 Data Sources — All Free, No Keys

| Source | What It Provides | How |
|--------|-----------------|-----|
| 📈 **Yahoo Finance** | Stock price, market cap, P/E ratio, 30-day chart | `yfinance` library |
| 📰 **Google News RSS** | Latest news articles + sentiment scoring | Public RSS feed |
| 📊 **Google Trends** | Search interest over time, trend direction, rising queries | `pytrends` |
| 💻 **GitHub API** | Tech stack, top repos, stars, commit activity | Public REST API |
| 📋 **SEC Edgar** | Official 10-K / 10-Q filings with direct links | US Gov API |
| 🚀 **Product Hunt** | Product launches, upvotes, community traction | Public RSS feed |
| 🏢 **Wikipedia + Wikidata** | Founded year, HQ, description, funding mentions | Free REST APIs |
| 🗣️ **Reddit** | Community mentions, sentiment, top discussions | Public JSON API |
| 👔 **Job Boards** | Open roles → hiring trends, growth phase inference | Greenhouse + Lever APIs |

> **No credit card. No accounts. No rate limits on most sources.**  
> The only key you need is a free [Groq API key](https://console.groq.com) to power the AI analysis.

---

## 🖥️ Analysis Tabs

| Tab | What You Get |
|-----|-------------|
| 📊 **Overview** | Executive summary, key metrics (price, market cap, GitHub stars, open roles) |
| 💰 **Financials** | Stock analysis, funding history, SEC filings, 30-day price chart |
| 📰 **News & Sentiment** | Latest headlines, Reddit discussions, sentiment breakdown |
| 💻 **Tech & GitHub** | Tech stack, top repos, developer mindshare, search trends chart |
| 🚀 **Products & Launches** | Product Hunt history, most recent launch, upvote traction |
| 👔 **Hiring Intel** | Role breakdown (Eng/Sales/Marketing/Product), inferred growth phase |
| ⚔️ **SWOT Analysis** | AI-generated Strengths / Weaknesses / Opportunities / Threats using all live data |
| 📋 **Raw Data** | Full JSON output per source + one-click download |

---

## 🚀 Quick Start

### Deploy to Streamlit Cloud (recommended)

1. **Fork this repo** on GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → connect your fork
3. In **Settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your_key_here"
   ```
4. Click **Deploy** — done!

### Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/competitor-intelligence-ai
cd competitor-intelligence-ai

pip install -r requirements.txt

# Add your Groq key
echo 'GROQ_API_KEY=your_key_here' > .env

streamlit run app.py
```

Get a free Groq key at [console.groq.com](https://console.groq.com) — no credit card needed.

---

## 📁 Project Structure

```
competitor-intelligence-ai/
│
├── app.py                        ← Streamlit UI + AI analysis (8 tabs)
├── requirements.txt              ← All dependencies
├── .env.example                  ← Environment variable template
│
├── agents/
│   ├── __init__.py               ← Empty (required for Python package)
│   └── realtime_agent.py         ← Parallel orchestrator (runs all 9 scrapers)
│
└── scrapers/
    ├── __init__.py               ← Empty (required for Python package)
    ├── yahoo_finance.py          ← Stock data via yfinance
    ├── newsapi_scraper.py        ← News via Google News RSS
    ├── google_trends.py          ← Search trends via pytrends
    ├── github_scraper.py         ← Tech stack via GitHub REST API
    ├── sec_edgar.py              ← Filings via SEC EDGAR API
    ├── product_hunt.py           ← Launches via Product Hunt RSS
    ├── crunchbase_scraper.py     ← Company data via Wikipedia + Wikidata
    ├── twitter_scraper.py        ← Mentions via Reddit public API
    └── job_boards.py             ← Hiring data via Greenhouse + Lever
```

---

## ⚙️ How It Works

```
  You type a company name
          │
          ▼
  ┌───────────────────────────────────────────┐
  │   9 scrapers run in parallel (6 threads)  │
  │                                           │
  │  Yahoo Finance  · Google News RSS         │
  │  Google Trends  · GitHub API              │
  │  SEC Edgar      · Product Hunt RSS        │
  │  Wikipedia/Wikidata · Reddit API          │
  │  Greenhouse + Lever Job APIs              │
  └───────────────────────────────────────────┘
          │
          ▼
  ┌───────────────────────────────────────────┐
  │   Context builder formats all raw data    │
  │   into structured markdown for the LLM   │
  └───────────────────────────────────────────┘
          │
          ▼
  ┌───────────────────────────────────────────┐
  │   Groq AI (Llama 3.1) analyses each tab  │
  │   grounded in the real-time data         │
  └───────────────────────────────────────────┘
          │
          ▼
  Streamlit dashboard + JSON export
```

---

## 📝 Example Companies to Research

| Category | Examples |
|----------|---------|
| **Payments / Fintech** | Stripe, Plaid, Brex, Ramp |
| **AI / LLM** | OpenAI, Anthropic, Mistral, Hugging Face |
| **Developer Tools** | Vercel, Supabase, Linear, Render |
| **SaaS** | Notion, Figma, Airtable, Intercom |
| **Public Tech** | Shopify, Atlassian, Twilio, Cloudflare |

> **Note:** Yahoo Finance and SEC Edgar only work for publicly listed US companies. All other sources work for any company.

---

## ⚠️ Source Limitations

| Source | Limitation |
|--------|-----------|
| Yahoo Finance | Public companies only (NYSE / NASDAQ listed) |
| SEC Edgar | US public companies only |
| Google Trends | Google rate-limits heavily — may occasionally fail on shared Streamlit Cloud IPs; retries automatically |
| GitHub | 60 req/hr without token (sufficient for normal use) |
| Job Boards | Only works for companies using Greenhouse or Lever ATS |
| Wikipedia / Wikidata | Private or very new companies may have sparse data |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Groq (Llama 3.1 8B) — free tier, fast inference |
| **Framework** | LangChain — agent orchestration |
| **UI** | Streamlit — dashboard + one-click cloud deployment |
| **Data** | requests, BeautifulSoup, trafilatura, yfinance, pytrends |
| **Parallelism** | `concurrent.futures.ThreadPoolExecutor` |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-data-source`)
3. Commit your changes
4. Open a pull request

Ideas welcome — especially new free data sources, better sentiment analysis, or export formats.

---

## 📄 License

MIT License — free for personal and commercial use.

---

**Built with ❤️ using 100% open-source, zero-cost tools**

⭐ Star this repo if you find it useful!
