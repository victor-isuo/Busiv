# 📡 Busiv — Autonomous Business Intelligence

An autonomous AI pipeline that monitors industry signals, synthesises findings using LangGraph reasoning, and delivers structured intelligence briefings daily — with no human initiation required.

Demonstrated on Nigerian fintech — configurable for any domain.

## 🔴 Live Demo

[https://victorisuo-busiv.hf.space](https://victorisuo-busiv.hf.space)

---

## What This Is

Most business intelligence tools wait for you to ask a question. Busiv runs while you sleep.

Every 6 hours it ingests articles from configured sources. Every morning at a scheduled time it synthesises the last 24 hours of intelligence into a structured briefing — categorised by regulatory, product, market, and hiring signals — and delivers it to a dashboard and email. No user query. No human trigger. The system executes autonomously.

This is the fourth distinct AI engineering pattern in this portfolio:

| Pattern | System | Execution Model |
|---------|--------|----------------|
| RAG + Agentic Reasoning | Industrial AI Copilot | Human-initiated queries |
| Evaluation Infrastructure | AgentEval | CI/CD triggered/Human-initiated |
| Multi-Agent Legal Analysis | LexAI | Document-initiated pipeline |
| **Autonomous Pipeline** | **Busiv** | **Schedule-driven, no human input** |

---

## System Architecture

```
APScheduler (configurable timezone)
        ↓
┌──────────────────────────────────────────┐
│         Ingestion Layer (every 6h)       │
│  RSS feeds · Relevance scoring           │
│  SHA256 deduplication · ChromaDB store   │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│      LangGraph Synthesis (daily)         │
│  Load articles node                      │
│  → Synthesise node (Groq Llama 4 Scout)  │
│  → Parse structured JSON output          │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│           Delivery Layer                 │
│  Dashboard (FastAPI + HTML)              │
│  Email (SendGrid HTTP API, HTML format)  │
│  JSONL persistence for history           │
└──────────────────────────────────────────┘
```

---

## What Makes This Different From a News Aggregator

**Relevance scoring before storage.** Articles are scored against a configurable watchlist of target companies and regulatory bodies. Only articles scoring above threshold are indexed. The synthesis agent never sees noise.

**Four signal categories.** Every finding is classified as Regulatory, Product, Market, or Hiring — not just "news." A policy circular gets different treatment from a funding round.

**Priority alert layer.** When the synthesis agent detects a regulatory or urgent market signal, a breaking alert banner fires at the top of the dashboard. High-priority signals are surfaced automatically — most teams monitor these manually.

**LangGraph synthesis — not summarisation.** The synthesis node receives all articles from the last 24 hours and produces a structured JSON briefing with findings, citations, significance ratings, and a priority alert determination. This is reasoning across sources, not concatenated summaries.

**Structured output with citations.** Every finding in the briefing cites the source article and URL. Decision-makers can trace every claim to its origin.

---

## Intelligence Coverage — Nigerian Fintech Configuration

The current deployment monitors the Nigerian fintech ecosystem. This configuration can be replaced entirely via `src/ingestion/sources.py`.

**Watchlist — 10 Companies**
Flutterwave · Moniepoint · Paystack · Kuda Bank · Cowrywise · PiggyVest · Carbon Nigeria · Risevest · OPay · PalmPay

**Regulatory Bodies**
CBN · SEC Nigeria · NDIC · FCCPC

**Signal Categories**

| Category | What It Tracks |
|----------|----------------|
| Regulatory | Policy changes, licensing, circulars, penalties |
| Product | New features, rates, partnerships, app launches |
| Market | Funding rounds, expansions, acquisitions, executive moves |
| Hiring | Engineering surges, new offices, key departures |

**Sources (9 feeds)**
TechCabal · Techpoint Africa · Nairametrics · BusinessDay · The Punch Business · Disrupt Africa · Africa Fintech Summit · Finextra · TechCrunch Fintech

---

## The Regulatory Layer — Why It Matters

Nigerian fintechs are acutely sensitive to CBN and SEC policy changes. A new circular can alter KYC requirements, payment limits, licensing conditions, or operational restrictions overnight. Most compliance teams monitor this manually — checking websites, setting Google Alerts that miss context, reading PDFs after the fact.

Busiv's regulatory signal layer detects high-priority mentions, classifies them automatically, fires a dashboard alert, and delivers a structured explanation of what changed and why it matters. That is a genuine enterprise pain point being solved autonomously.

---

## Extending This System

Busiv is configured for Nigerian fintech intelligence, but the architecture is domain-agnostic. The watchlist, RSS sources, signal categories, and monitored entities are defined in a single configuration file — `src/ingestion/sources.py`. Pointing this pipeline at a different domain requires only:

- Replacing the RSS feed URLs with relevant sources
- Updating the watchlist with target companies or institutions
- Redefining the signal categories to match the domain
- Adjusting the timezone and schedule to the target region

The same autonomous pipeline can monitor European fintech regulations, US healthcare policy, SaaS competitive intelligence, or any information domain where scheduled synthesis adds value over manual monitoring.

---

## Schedule

| Job | Frequency | Time |
|-----|-----------|------|
| Feed Ingestion | Every 6 hours | 00:00, 06:00, 12:00, 18:00 WAT |
| Synthesis + Delivery | Daily | 07:00 WAT |

Both jobs run autonomously. Manual triggers available via dashboard buttons and API endpoints for on-demand briefings.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/briefings` | GET | Recent briefings list |
| `/briefings/latest` | GET | Latest briefing JSON |
| `/briefings/{id}` | GET | Specific briefing by ID |
| `/trigger/ingestion` | POST | Manual ingestion trigger |
| `/trigger/synthesis` | POST | Manual synthesis + delivery trigger |
| `/scheduler/status` | GET | Scheduler job status and next run times |
| `/store/stats` | GET | ChromaDB store statistics |
| `/health` | GET | System health check |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scheduling | APScheduler 3.11 — AsyncIOScheduler |
| Synthesis Agent | LangGraph — 3-node stateful pipeline |
| LLM | Groq Llama 4 Scout 17B |
| Ingestion | feedparser + httpx + BeautifulSoup |
| Vector Store | ChromaDB + all-MiniLM-L6-v2 |
| Email Delivery | SendGrid HTTP API (httpx) |
| API | FastAPI 0.136 |
| Deployment | Hugging Face Spaces (Docker) |
| Timezone | Configurable (default: Africa/Lagos, WAT UTC+1) |

---

## Local Setup

```bash
git clone https://github.com/victor-isuo/busiv.git
cd busiv
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

Create `.env`:

```
GROQ_API_KEY=your_groq_key
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=busiv

# Email delivery (SendGrid)
SENDGRID_API_KEY=your_sendgrid_api_key
EMAIL_FROM=your_verified_sender@email.com
EMAIL_TO=recipient@email.com

# Schedule (defaults to 07:00 Lagos time — adjust for your timezone)
PIPELINE_SCHEDULE_HOUR=7
PIPELINE_SCHEDULE_MINUTE=0
PIPELINE_TIMEZONE=Africa/Lagos

PORT=7860
```

Run:

```bash
uvicorn main:app --reload --port 7860
```

Open `http://localhost:7860`. On startup, Busiv runs an immediate ingestion cycle. Click **⚡ Generate Briefing** for the first intelligence edition.

---

## Project Structure

```
busiv/
├── src/
│   ├── ingestion/
│   │   ├── sources.py          # Watchlist, RSS feeds, signal keywords
│   │   ├── feed_ingestor.py    # Ingestion, dedup, relevance scoring
│   │   └── scheduler.py        # APScheduler configuration
│   ├── synthesis/
│   │   └── briefing_agent.py   # LangGraph synthesis pipeline
│   ├── delivery/
│   │   ├── email_sender.py     # HTML email via SendGrid HTTP API
│   │   └── report_store.py     # JSONL persistence
│   └── api/
├── static/
│   └── index.html              # Dashboard UI
├── data/                       # Auto-created at runtime
├── main.py                     # FastAPI application
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Production Notes

**Email delivery.** HuggingFace Spaces blocks outbound SMTP on ports 587 and 465. Busiv uses the SendGrid HTTP API as a workaround. Local development can use Gmail SMTP with an app password instead.

**Scheduler persistence.** APScheduler runs in-memory on HuggingFace Spaces. If the Space goes cold, the scheduler reinitialises on the next request. Manual triggers via the dashboard ensure a briefing can always be generated on demand.

---

## Relationship to Other Portfolio Systems

Busiv represents the autonomous execution pattern in a four-system AI engineering portfolio:

*"I've applied AI reasoning across four distinct execution models: an industrial fault diagnosis platform that responds to engineer queries in real time using hybrid RAG and LangGraph agentic reasoning; an LLM evaluation platform with CI/CD regression gates that automatically blocks performance regressions; an AI contract intelligence system where four CrewAI specialist agents sequentially analyse legal documents and surface risk across 80+ Common Law jurisdictions; and an autonomous intelligence pipeline that monitors a target domain daily without human input — synthesising findings across sources and delivering structured briefings on a schedule. Every system is deployed, live, and built against real production constraints."*

---

## Disclaimer

Busiv produces AI-synthesised intelligence briefings for informational purposes. Findings are derived from publicly available news sources. Not financial advice. Not investment advice.

---

## Author

**Victor Isuo** — Applied LLM Systems Engineer

[GitHub](https://github.com/victor-isuo) · [LinkedIn](https://linkedin.com/in/victor-isuo-a02b65171) · [Industrial AI Copilot](https://victorisuo-industrial-ai-copilot.hf.space) · [AgentEval](https://victorisuo-agenteval.hf.space) · [LexAI](https://victorisuo-lexai.hf.space/ui) · [Busiv](https://victorisuo-busiv.hf.space)
