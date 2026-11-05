# B2B Sales Agent — Multi-Agent Cold Email Generator

An AI multi-agent pipeline that researches a company and produces a highly personalized,
review-passed cold outreach email. Built around 5 cooperating agents:

1. **Research Agent** — pulls live web data about a company and structures it as JSON
2. **Hook Extractor Agent** — finds the 3 strongest personalization angles
3. **Email Writer Agent** — drafts a short (≤4 sentence) cold email using the best hook
4. **Email Reviewer Agent** — grades the draft against 5 pass/fail criteria and rewrites it if it fails (up to 3 attempts)
5. **Orchestrator** — chains the above and enforces guardrails (dedupe, rate limiting, real citations only)

## Why this differs from the original prompt pack

The original 5-prompt package assumed `{search_results}` would magically already exist.
In practice an LLM can't browse Crunchbase or LinkedIn by itself, so this build wires in
a **real web search step** (Tavily, free tier) before the Research Agent ever sees the company.
That's the difference between a prompt package and something a client can actually run.

Two other changes from the original spec, based on real deliverability concerns:

- **No invented reply-rate stats.** The original portfolio copy claimed "8-12% reply rates" —
  a number nobody can back up before running real campaigns. The orchestrator's output never
  fabricates performance metrics; it only reports what it actually did (attempts, sources used).
- **Dedupe + rate limiting.** A local SQLite ledger prevents the same company being emailed
  twice and caps how many companies can be processed per run, so this can't accidentally be
  used to spam a list.

## Stack

- **FastAPI** — HTTP service, matches your existing stack
- **Groq** (`llama-3.3-70b-versatile` by default) — fast, generous free tier for all 4 LLM agents
- **Tavily** — free-tier web search API for the Research Agent's live data
- **SQLite** — local dedupe/rate-limit ledger (`sent_log.db`), zero setup

Both Groq and Tavily have free API keys — no paid infra needed to demo this on Upwork.

## What changed in this version 

This version adds the two things that actually move an Upwork proposal:

- **`app_ui.py`** — a Streamlit demo you run with one command and screen-share live: type a
  company name, watch it research → hook → draft → self-review in real time. This is what
  you record for your portfolio video, not the API.
- **Batch mode** (`/generate-emails-batch` and the "Batch (CSV)" tab in the UI) — upload a
  CSV of leads, get emails for all of them. This is the actual use case a client has (a lead
  list), not one company at a time.
- **`processing_time_seconds`** on every result — the first question a buyer asks is "how
  fast/cheap is this per lead," so the number is in the response, not something you have to
  estimate on a call.

## Setup

```bash
cd b2b_sales_agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in GROQ_API_KEY and TAVILY_API_KEY in .env (both free to obtain)
```

Get keys:
- Groq: https://console.groq.com/keys
- Tavily: https://app.tavily.com

## Run

```bash
uvicorn app.main:app --reload
```

Then either hit the API directly:

```bash
curl -X POST http://localhost:8000/generate-email \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Webflow", "company_url": "https://webflow.com"}'
```

or run the included example script:

```bash
python tests/test_example.py
```

or, better for a  demo, launch the UI:

```bash
streamlit run app_ui.py
```

This opens a browser tab where you type a company name and URL, watch the pipeline run live,
and can expand the hooks/research/review-feedback for each result. There's also a "Batch (CSV)"
tab — try it with the included `sample_companies.csv`. 
## API

### `POST /generate-email`

**Body:**
```json
{ "company_name": "Webflow", "company_url": "https://webflow.com" }
```

**Response:**
```json
{
  "subject_line": "...",
  "email_body": "...",
  "hooks_considered": ["...", "...", "..."],
  "selected_hook": "...",
  "review_status": "PASSED after 1 attempt",
  "review_feedback": [],
  "sources_used": ["https://...", "..."],
  "research_data": { "...": "..." }
}
```

### `POST /generate-emails-batch`

Multipart file upload, CSV with `company_name,company_url` columns. Runs the full pipeline
per row; one failed or duplicate row never aborts the rest. Returns a summary plus a
per-company status (`success`, `skipped_duplicate`, `rate_limited`, `failed`).

### `GET /sent-log`
Returns the dedupe ledger — every company already processed, and when.

### `DELETE /sent-log/{company_name}`
Removes a company from the ledger if you want to re-run it intentionally.

## How dedupe & rate limiting work

- Before running the pipeline, the orchestrator checks `sent_log.db` for the company name
  (case-insensitive). If it's already there, the API returns `409 Conflict` with the prior result
  instead of silently re-generating and re-"sending" an email to the same lead.
- A simple in-memory sliding-window limiter caps requests per minute (`RATE_LIMIT_PER_MINUTE`
  in `.env`, default 10) so a runaway script or loop can't hammer your Groq/Tavily quota or,
  worse, blast a lead list unattended.



## File structure

```
b2b_sales_agent/
├── app/
│   ├── main.py            FastAPI app + endpoints (single + batch)
│   ├── config.py          env var loading
│   ├── schemas.py         Pydantic models for every agent's I/O
│   ├── llm_client.py      Groq wrapper with JSON-mode parsing + retries
│   ├── search_client.py   Tavily wrapper for live company research
│   ├── db.py              SQLite dedupe/rate-limit ledger
│   └── agents/
│       ├── research_agent.py
│       ├── hook_extractor.py
│       ├── email_writer.py
│       ├── email_reviewer.py
│       └── orchestrator.py
├── app_ui.py               Streamlit demo — record this for your portfolio
├── sample_companies.csv    sample lead list for the batch demo
├── tests/
│   └── test_example.py    runs the Webflow example end-to-end
├── requirements.txt
├── .env.example
└── README.md
```
