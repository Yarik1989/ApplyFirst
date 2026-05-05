# ApplyFirst

**Be the first 10 applicants on every job that matters.**

ApplyFirst is an AI-powered job alert system that monitors job boards and
direct employer career pages in real time, scores each posting against your
resume, tailors your resume per posting with Claude, and pings you on
Telegram with Approve / Skip buttons — so you never miss a fresh listing.

Built first for registered nurses in the Sacramento metro, but the
architecture is role-agnostic and works for any job seeker willing to define
their target keywords and employers.

---

## Why it exists

Hospital and corporate ATS systems heavily favor applicants who apply within
the first hour of a posting going live. By the time a listing surfaces on
aggregator inboxes or daily digests, hundreds of resumes are already in the
queue. ApplyFirst closes that gap:

- **5-minute polling** across RSS feeds and direct employer careers pages
- **ATS keyword scoring** against a structured resume, so low-fit jobs are
  filtered out before they ever hit your phone
- **Claude-tailored resume patches** — small wording diffs, not full
  rewrites, preserving your voice and credentialing
- **Interview prep pack** generated per approved posting from real candidate
  feedback (Glassdoor, Indeed reviews, Reddit)
- **Human approval gate** before any application is submitted — no silent
  auto-apply, no bot-flagging patterns

---

## Goals

1. **Speed** — surface qualifying postings within 5 minutes of publication.
2. **Relevance** — never notify on a job scoring below the configured ATS
   threshold; no LVN/CNA/NP noise when the target is RN.
3. **Signal over volume** — hard cap of 15 applications per day, quality
   first.
4. **Safety** — every application requires a human tap; all timing jittered
   to look human; scraping respects robots.txt and rate limits.
5. **Portability** — SQLite + Python now, Postgres + FastAPI + Next.js when
   it becomes multi-user. No lock-in to a single stack or vendor.

---

## Architecture

```
                ┌────────────────────────┐
                │   APScheduler (5 min)  │
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │   Scrapers (async)     │
                │  ├── RSS feeds         │  Indeed, LinkedIn, ZipRecruiter
                │  └── Direct scrapers   │  Kaiser, Sutter, UC Davis, Dignity
                └───────────┬────────────┘
                            │ new postings
                ┌───────────▼────────────┐
                │  Dedup (seen_jobs)     │  SQLite
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │  ATS scorer (Phase 2)  │  keyword match against resume JSON
                └───────────┬────────────┘
                            │ score ≥ threshold
                ┌───────────▼────────────┐
                │  Resume tailor (P2)    │  Claude API → JSON patch → PDF/DOCX
                └───────────┬────────────┘
                            │ 2–8 min jitter (anti-flag)
                ┌───────────▼────────────┐
                │  Telegram notifier     │  Approve / Skip inline buttons
                └───────────┬────────────┘
                            │ Approve tap
                ┌───────────▼────────────┐
                │  Interview prep (P2)   │  Glassdoor + Reddit + Claude
                └───────────┬────────────┘
                            │
                ┌───────────▼────────────┐
                │  Apply manager (P2)    │  Playwright, rate-limited, visible
                │                        │  browser, max 15/day
                └────────────────────────┘
```

### Phase 1 — Job monitor + Telegram bot (current)
- Python 3.11+, APScheduler, feedparser, httpx + BeautifulSoup4
- aiosqlite for dedup (`seen_jobs`, `alerts` tables)
- python-telegram-bot 20+ (async), inline Approve/Skip callbacks
- All secrets in `.env`

### Phase 2 — AI layer
- `anthropic` SDK — Claude for ATS scoring, resume tailoring, interview prep
- Structured resume in `assets/resume_base.json` → JSON diff patches → PDF
  via reportlab, DOCX via python-docx
- Interview prep generator: scrapes aggregated candidate feedback per
  employer, synthesises a Q&A pack with STAR-structured drafts, delivers as
  a Telegram message + PDF attachment

### Phase 3 — Web UI + multi-user
- FastAPI backend with JWT auth, Postgres (migrate from SQLite)
- Next.js 14 frontend (app router)
- Stripe subscriptions for the Pro tier
- Hosted on Vercel (frontend) + Railway or Hetzner VPS (backend)

---

## Project structure

```
ApplyFirst/
├── CLAUDE.md                  ← full design doc + decisions (canonical)
├── README.md                  ← you are here
├── .env.example
├── docker-compose.yml
├── requirements.txt
│
├── backend/
│   ├── main.py                ← entry point, starts APScheduler
│   ├── config.py              ← loads .env
│   ├── database.py            ← SQLite, seen_jobs + alerts tables
│   ├── scrapers/              ← RSS + direct hospital scrapers
│   ├── notifier/              ← Telegram bot, email digest
│   ├── ai/                    ← scorer, tailor, resume builder, interview prep
│   ├── research/              ← Glassdoor, Indeed reviews, Reddit sources
│   └── apply/                 ← Playwright fillers (Workday, Taleo)
│
├── assets/
│   ├── resume_base.json       ← structured resume for AI scoring
│   ├── resume_base.pdf        ← current resume file
│   └── prep/                  ← generated interview prep PDFs
│
├── frontend/                  ← Phase 3, Next.js 14
└── tests/
```

See `CLAUDE.md` for the canonical architecture, decisions, and open
questions — this README is the friendly overview.

---

## Anti-flagging rules

These are non-negotiable and enforced in code:

- Human approval gate before every application — no auto-apply
- Random 2–8 minute delay between job discovery and Telegram notification
- Random 45–90 second delay when filling application forms
- Hard cap: 15 applications per day per user
- RSS feeds preferred; HTML scraping only when no feed exists
- Playwright runs with a visible (non-headless) browser + real user profile
- Never submit two applications within 60 seconds of each other
- Research scrapers (Glassdoor, Reddit) cache per-employer for 14 days,
  respect robots.txt, back off on 429s

---

## Quick start

```bash
# 1. clone + install
git clone <repo>
cd ApplyFirst
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. configure
cp .env.example .env
# edit .env — add TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY

# 3. run
python -m backend.main
```

Or via Docker:

```bash
docker compose up --build
```

---

## Configuration

All configuration lives in `.env`. Key variables:

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_CHAT_ID` | From @userinfobot |
| `ANTHROPIC_API_KEY` | Claude API key (Phase 2+) |
| `POLL_INTERVAL_MINUTES` | Scraper cadence, default 5 |
| `MAX_APPLIES_PER_DAY` | Hard cap, default 15 |
| `MIN_ATS_SCORE_THRESHOLD` | Skip below this score, default 60 |
| `NOTIFY_DELAY_MIN_SECONDS` / `_MAX_` | Anti-flag jitter, 120–480 |
| `SEARCH_KEYWORDS` | Comma-separated target keywords |
| `SEARCH_LOCATION` / `_RADIUS_MILES` | Geography |

See `.env.example` for the full list.

---

## Roadmap

- [x] Resume optimised (PDF + DOCX, ATS ~85% avg)
- [x] Architecture designed
- [x] Project scaffolding
- [ ] **Phase 1** — job monitor + Telegram bot (in progress)
- [ ] **Phase 2** — Claude scoring, resume tailoring, interview prep
- [ ] **Phase 3** — web UI, multi-user, Stripe
- [ ] Public launch (Product Hunt, r/nursing, Show HN)

---

## Business model

- **Open source (MIT)** — self-host free forever
- **Free hosted tier** — 3 sources, email, 5 alerts/day
- **Pro $9/mo** — unlimited sources, Telegram, AI resume patching, interview
  prep packs, apply assist
- **Teams $29/mo** — multiple profiles (staffing agencies, nursing schools)

---

## License

MIT. See `LICENSE`.
