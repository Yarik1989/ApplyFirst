# ApplyFirst — Project Memory for Claude Code

This file is read automatically by Claude Code at the start of every session.
It contains all context, decisions, and architecture agreed in the design phase.
Do not delete or rename this file.

---

## What this project is

ApplyFirst is an AI-powered job alert system built for nurses (and any job seeker)
that monitors job boards and direct hospital career pages in real time, scores each
posting against the user's resume using ATS keyword matching, tailors the resume
slightly per posting via Claude API, sends an instant Telegram notification with
Approve/Skip buttons, and (Phase 2+) auto-fills the application after approval.

The #1 goal: get the user into the first 10 applicants on every relevant posting.

---

## The user this was built for first

Hanna Safronova, RN — Roseville, CA
- Registered Nurse licensed in California (#95452319) and New York (#986427)
- Background: MD-equivalent degree (Kharkiv National Medical University, Ukraine)
- 18+ months physician intern experience in neurology, acute inpatient care
- Target roles: RN – Acute Care, Medical-Surgical, Neurology, Cardiology
- Target employers: Kaiser Permanente, Sutter Roseville, UC Davis Health,
  Dignity Health, Adventist Health Roseville, Placer County Public Health
- Location: Roseville CA — search radius 50 miles (Sacramento metro)
- Notification channel: Telegram (already uses it daily)
- Languages: English, Ukrainian, Russian (trilingual — a key differentiator)

---

## Target job keywords

Primary:
  "Registered Nurse", "RN", "Nurse", "Med-Surg", "Medical-Surgical",
  "Acute Care", "Neurology", "Cardiology", "Telemetry"

Note: bare "Nurse" was added 2026-04-15 because hospital postings often drop
the RN prefix (e.g. "Nurse Pre Post Procedure" at Mercy San Juan / Dignity).
Exclusion list filters non-RN noise (LVN, CNA, NP, Travel Nurse).

Secondary (include in scoring but don't filter on):
  "ICU", "Critical Care", "Float Pool", "Per Diem", "Part Time", "Full Time"

Exclude:
  "LVN", "CNA", "NP", "Nurse Practitioner"
  All travel nursing: "Travel Nurse", "Travel Nursing", "Travel RN",
    "Travel Registered", "Travel ICU", "Travel PACU", "Travel CVOR",
    "Travel L&D", "Travel Endoscopy", "Travel Radiology", "Travel Med-Surg"
  Senior RN levels: "Registered Nurse II/III/IV", "RN II/III/IV"
  (Travel + senior excluded 2026-04-15: Hanna is a new grad — agencies
  won't consider her for travel; II+ levels require 1+ years acute exp.)

---

## Architecture decisions (agreed, do not change without discussion)

### Phase 1 — Build first (current phase)
- Python 3.11+
- APScheduler — polls every 5 minutes
- feedparser — RSS feeds for Indeed, LinkedIn, ZipRecruiter
- httpx + BeautifulSoup4 — direct scraping for Kaiser, Sutter, UC Davis, Dignity
- aiosqlite — SQLite database, seen_jobs table to prevent duplicate alerts
- python-telegram-bot 20+ (async) — instant notifications with inline buttons
- .env for all secrets — never hardcoded

### Phase 2 — AI layer (next)
- anthropic SDK — Claude API for ATS scoring and resume tailoring
- Resume stored as structured JSON (assets/resume_base.json)
- Claude returns a JSON diff of suggested wording changes only (not full rewrite)
- reportlab + python-docx — regenerate PDF and DOCX with patches applied
- Interview prep generator — per-posting Q&A pack built from the job description
  + aggregated candidate feedback (Glassdoor, Indeed reviews, Reddit r/nursing,
  Blind). Sent to Telegram as a second message after the approval tap.

### Phase 3 — Web UI (later)
- FastAPI backend with JWT auth
- Next.js 14 frontend (app router)
- PostgreSQL (swap SQLite when multi-user)
- Stripe for $9/mo Pro tier
- Hosted on Vercel (frontend) + Railway or Hetzner VPS (backend)

### Anti-flagging rules (never remove these)
- Human approval gate before EVERY application — no auto-apply without tap
- Random 2–8 minute delay between job discovery and Telegram notification
- Random 45–90 second delay when filling application forms
- Hard cap: max 15 applications per day per user
- Use RSS feeds where available — only scrape HTML when no feed exists
- Playwright must run with visible (non-headless) browser + real user profile
- Never submit multiple applications within 60 seconds of each other

---

## Project structure

```
ApplyFirst/
├── CLAUDE.md                  ← you are here
├── README.md
├── .env.example
├── .env                       ← never commit, in .gitignore
├── docker-compose.yml
├── requirements.txt
│
├── backend/
│   ├── main.py                ← entry point, starts APScheduler
│   ├── config.py              ← loads .env, single source of settings
│   ├── database.py            ← SQLite setup, seen_jobs + alerts tables
│   │
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py            ← abstract BaseScraper class
│   │   ├── rss_scraper.py     ← Indeed, LinkedIn, ZipRecruiter RSS
│   │   ├── kaiser_scraper.py  ← Kaiser Permanente careers direct
│   │   ├── sutter_scraper.py  ← Sutter Health careers direct
│   │   ├── ucdavis_scraper.py ← UC Davis Health careers direct
│   │   └── dignity_scraper.py ← Dignity Health careers direct
│   │
│   ├── notifier/
│   │   ├── telegram_bot.py    ← send alerts, handle Approve/Skip callbacks
│   │   └── email_notifier.py  ← daily digest (Phase 2)
│   │
│   ├── ai/                    ← Phase 2
│   │   ├── scorer.py          ← ATS keyword match scoring
│   │   ├── tailor.py          ← Claude API resume patch
│   │   ├── resume_builder.py  ← regenerate PDF/DOCX
│   │   └── interview_prep.py  ← Q&A pack from JD + candidate feedback
│   │
│   ├── research/              ← Phase 2 — sources for interview prep
│   │   ├── glassdoor.py       ← interview reviews + questions scrape
│   │   ├── indeed_reviews.py  ← company reviews
│   │   ├── reddit.py          ← r/nursing + role-specific subs (PRAW)
│   │   └── blind.py           ← optional, if accessible
│   │
│   └── apply/                 ← Phase 2
│       ├── apply_manager.py   ← approval queue, rate limiter
│       ├── workday_filler.py  ← Playwright Workday
│       └── taleo_filler.py    ← Playwright Taleo
│
├── frontend/                  ← Phase 3
│   └── (Next.js 14 app)
│
├── assets/
│   ├── resume_base.json       ← Hanna's resume as structured data
│   └── resume_base.pdf        ← current resume file
│
└── tests/
    ├── test_scrapers.py
    ├── test_scorer.py
    ├── test_interview_prep.py
    └── test_telegram.py
```

---

## Environment variables (see .env.example)

```
# Telegram
TELEGRAM_BOT_TOKEN=          # from @BotFather
TELEGRAM_CHAT_ID=            # your personal chat ID from @userinfobot

# Anthropic
ANTHROPIC_API_KEY=           # from console.anthropic.com

# Scheduler
POLL_INTERVAL_MINUTES=5
MAX_APPLIES_PER_DAY=15
MIN_ATS_SCORE_THRESHOLD=60   # skip jobs below this score

# Notifications
NOTIFY_DELAY_MIN_SECONDS=120   # min delay before sending alert (anti-flag)
NOTIFY_DELAY_MAX_SECONDS=480   # max delay before sending alert (anti-flag)

# Job search
SEARCH_KEYWORDS=Registered Nurse,RN,Med-Surg,Acute Care,Neurology
SEARCH_LOCATION=Roseville CA
SEARCH_RADIUS_MILES=50

# Database
DATABASE_PATH=./data/applyfirst.db
```

---

## RSS feed URLs (confirmed working)

```
Indeed RN Roseville:
https://www.indeed.com/rss?q=registered+nurse&l=Roseville+CA&radius=50&sort=date

LinkedIn RN Sacramento:
https://www.linkedin.com/jobs/search/?keywords=registered+nurse&location=Sacramento+CA&f_TPR=r300&sortBy=DD

ZipRecruiter RN:
https://www.ziprecruiter.com/jobs-search?search=registered+nurse&location=Roseville+CA&radius=50
```

---

## Resume data (Hanna — structured for AI scoring)

```json
{
  "name": "Hanna Safronova, RN",
  "location": "Roseville, CA",
  "licenses": ["CA RN #95452319", "NY RN #986427", "BLS-AHA", "CCMA-AMCA"],
  "target_roles": ["Registered Nurse", "Acute Care RN", "Med-Surg RN", "Neurology RN"],
  "keywords": [
    "patient assessment", "vital signs monitoring", "telemetry monitoring",
    "cardiac monitoring", "neurological assessment", "med-surg nursing",
    "acute inpatient care", "care planning", "patient safety",
    "fall prevention protocol", "infection prevention",
    "isolation precautions", "wound care", "skin integrity assessment",
    "pain assessment", "blood glucose monitoring", "urinary catheterization",
    "Foley catheter", "phlebotomy", "NG tube management",
    "medication administration", "IV", "IM", "SQ", "PO",
    "specimen collection", "BLS", "CPR", "rapid response", "Code Blue",
    "SBAR communication", "Epic EHR", "EMR", "clinical documentation",
    "NDNQI", "patient education", "care coordination", "interdisciplinary",
    "stroke protocol", "NIHSS", "seizure monitoring", "discharge planning",
    "immunizations", "chronic disease management",
    "culturally competent care", "multilingual", "English", "Ukrainian", "Russian"
  ],
  "experience": [
    {
      "title": "Clinical Physician Intern – Neurology (RN-Equivalent Scope)",
      "org": "Kharkiv Regional Clinical Hospital, Ukraine",
      "dates": "Aug 2020 – Feb 2022"
    },
    {
      "title": "Clinical Volunteer – ICU & Cardiology",
      "org": "Kharkiv Regional Clinical Hospital, Ukraine",
      "dates": "Jun – Sep 2019"
    },
    {
      "title": "Medical Assistant Extern",
      "org": "Sutter Medical Foundation – Internal Medicine, Auburn CA",
      "dates": "Feb – Mar 2024"
    }
  ],
  "education": [
    "BSN – In Progress, Ternopil Medical University, Ukraine (Exp. 2026)",
    "Doctor of Medicine (MD Equivalent), Kharkiv National Medical University (2014–2022)",
    "Clinical Medical Assistant Program, CAL Regional, Roseville CA (2023–2024)",
    "Diploma in Nursing, Kharkiv Basic Medical College No. 1 (2010–2014)"
  ]
}
```

---

## Git commit conventions

Use conventional commits so the history reads cleanly:
- `feat:` new feature
- `fix:` bug fix
- `chore:` setup, config, dependencies
- `docs:` README, CLAUDE.md updates
- `test:` adding tests

Example: `feat: Phase 1 — RSS scraper + Telegram bot`

---

## Interview prep generator (Phase 2 feature spec)

### Goal
After a posting is approved in Telegram, automatically produce a tailored
interview prep pack so Hanna walks in with high-signal, employer-specific
answers drawn from what real candidates and employees said about that role
and company.

### Trigger
Fires once per approved posting (Approve tap in Telegram → enqueue prep job).
Never run for skipped or sub-threshold postings — keeps Claude spend tied to
real intent.

### Inputs
- Structured job posting (title, employer, unit/specialty, location, JD text)
- Resume JSON (assets/resume_base.json) — to personalise answers
- Aggregated candidate feedback for that employer + role family:
  - Glassdoor interview reviews (questions asked, difficulty, outcome)
  - Glassdoor / Indeed company reviews (culture, management, pace, pain points)
  - Reddit threads from r/nursing, r/Kaiser, r/sutterhealth, r/ucdavis, etc.
  - Blind posts when accessible
- Role-generic clinical question bank (fallback when employer data is thin)

### Output — JSON schema (stored in `interview_packs` table)
```json
{
  "job_id": "uuid",
  "employer": "Kaiser Permanente",
  "role": "RN – Med-Surg",
  "generated_at": "ISO-8601",
  "sources": [{"type": "glassdoor", "url": "...", "scraped_at": "..."}],
  "questions": [
    {
      "q": "Tell me about a time you escalated a deteriorating patient.",
      "category": "clinical | behavioral | situational | company | logistics",
      "frequency": "high | medium | low",   // how often this employer asks it
      "source_count": 4,                    // how many candidates reported it
      "suggested_answer": "STAR-structured draft pulled from resume...",
      "why_they_ask": "Kaiser emphasises rapid response + SBAR — see reviews"
    }
  ],
  "company_insights": {
    "culture": "...",
    "red_flags": ["..."],
    "green_flags": ["..."],
    "questions_to_ask_them": ["..."]
  }
}
```

### Delivery
- Telegram: short summary message + PDF attachment (`prep_<jobid>.pdf`)
- PDF generated with reportlab, same style as the tailored resume
- Also written to `assets/prep/` for later review

### Anti-flagging / ethics rules (apply to research scrapers)
- Respect robots.txt; back off on 429s with exponential jitter
- Cache per-employer research for 14 days — don't re-scrape on every posting
- Attribute sources in the pack; never present scraped text as original
- No scraping of user profiles — only aggregated public interview reports
- If a source blocks us, fall back to role-generic bank, never spoof headers

### Claude API usage
- Single call per posting, model: `claude-opus-4-6` (deep synthesis)
- Use prompt caching for the resume JSON + role-generic question bank (stable
  prefix) — only the posting + fresh research is the variable tail
- Cap: 1 prep pack per approved job, 15/day ceiling inherited from apply cap

### Open questions (decide before building)
- [ ] Do we need a PRAW app registration for Reddit, or use Pushshift mirrors?
- [ ] Glassdoor gates scraping — acceptable to require a manual session cookie?
- [ ] Should prep packs be regenerated if the user doesn't interview within N days?

---

## Business model (for future reference)

- Open source (MIT) + hosted paid tier
- Free: 3 sources, email only, 5 alerts/day
- Pro $9/mo: unlimited sources, Telegram, AI resume patching, apply assist
- Teams $29/mo: multiple profiles (staffing agencies, nursing schools)
- Launch: Product Hunt + Reddit r/nursing + r/cscareerquestions + Show HN

---

## Current status

- [x] Resume optimised (PDF + DOCX generated, ATS score ~85% avg)
- [x] Architecture designed
- [x] Project structure agreed
- [ ] Phase 1: job monitor + Telegram bot
- [ ] Phase 2: Claude AI scoring + resume tailoring
- [ ] Phase 2: interview prep generator (JD + candidate feedback → Q&A pack)
- [ ] Phase 3: Web UI + user accounts
- [ ] Launch
