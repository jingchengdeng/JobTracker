# JobTracker

A local-first job application tracker with AI-powered resume tailoring, mock interviews, and LinkedIn contact discovery.

## Why I built this

Job hunting is a grind. You're juggling dozens of applications across different stages, tailoring resumes for each role, practicing for interviews, and trying to find the right people to reach out to at each company. I was doing all of this in spreadsheets and browser tabs, and it was falling apart.

So I built the tool I wished I had. One place to track every application, an AI agent that understands my resume and can tailor it to any JD, a mock interviewer that adapts to the role I'm targeting, and a search pipeline that finds the right contacts at each company without me manually combing through LinkedIn. Everything runs locally, my data stays mine, and I can swap LLM providers without changing a line of code.

## What it does

- **Track applications** -- add jobs manually or save from LinkedIn with one click. Filter, search, view details in a side panel.
- **Tailor resumes** -- a four-step agent pipeline analyzes the JD, finds gaps, suggests improvements, and rewrites your resume. Send follow-ups to refine; a classifier decides which steps to re-run.
- **Practice interviews** -- voice or text, three types (technical, behavioral, system design), five scoring dimensions with evidence from the transcript.
- **Find contacts** -- searches for recruiters, hiring managers, and department leads at the target company. Scores relevance and generates personalized connection notes.
- **Company enrichment** -- optional Apollo integration fetches company data and generates interview-prep summaries.

## Architecture

```
Next.js 16 (TypeScript)                     FastAPI (Python 3.12)
+---------------------------------+          +----------------------------------+
|                                 |          |                                  |
|  /applications  /resumes        |   REST   |  /api/runs      /api/extension   |
|  /analytics     /settings       | <------> |  /api/interview /api/embedding   |
|                                 |          |  /api/linkedin  /api/providers   |
|  SQLite (libsql + Drizzle ORM)  |    WS    |  SQLite (aiosqlite)              |
|  - jobs, goals, resumes         | <------> |  - ai_runs, ai_steps, ai_msgs    |
|  - preferences, interviews      |          |  - interview_*, linkedin_*       |
|                                 |          |                                  |
+---------------------------------+          +-----+---+---+---+---+---+--------+
                                                   |   |   |   |   |   |
                                                   v   v   v   v   v   v
                                             LLM Providers   ChromaDB
                                             (multi-provider    (RAG)
                                              registry)
```

### Agent provider registry

Every agent call goes through a role-based model config. Five roles, each independently assignable to any provider:

| Role | Default | What it powers |
|------|---------|----------------|
| **default** | gpt-5.4 | Resume pipeline agents (JD analysis, gap analysis, suggestions, rewrite) |
| **classifier** | gpt-4o-mini | Follow-up routing: decides which pipeline steps to re-run |
| **embedding** | text-embedding-3-small | Resume chunking and RAG retrieval via ChromaDB |
| **interview** | gpt-5.4-mini | Interview planning, turn processing, scoring |
| **linkedin** | gpt-4o-mini | JD analysis, relevance scoring, connection notes |

Supported providers: **OpenAI**, **Anthropic**, **Kimi**, **OpenRouter**, **OpenAI Codex** (OAuth). Each role supports a fallback provider/model for automatic failover.

## Agent workflows

Three LangGraph-orchestrated pipelines, one WebSocket-driven interview system, and a classifier agent. The Chrome extension triggers the full master pipeline with one click -- everything downstream runs automatically in the background.

### Master Pipeline: one click, 10-12 agent calls

This is the full workflow triggered by clicking "Save to JobTracker" on a LinkedIn job page. The extension captures raw DOM text, sends it to the backend, and gets an immediate response once the job is saved. All downstream processing runs in the background.

```
  LinkedIn page
       |
       v
  Chrome Extension
  (captures raw DOM text)
       |
       v
  /api/extension/extract
       |
       +---> Save raw text to file
       +---> Duplicate check (by URL) ---> "Already saved" (stop)
       |
       v
  +------------------+     +-----------+     +------------------+
  | Extraction Agent  |---->| Validate  |---->| Insert Job to DB |-----> Return to user
  | (agent call #1)   |     | (rules)   |     | (Next.js API)    |       "Saved to DB!"
  | Parses title,     |     |           |     |                  |
  | company, salary,  |     | fail?     |     |                  |
  | location, etc.    |     | retry w/  |     |                  |
  +------------------+     | feedback  |     +--------+---------+
                            +-----------+              |
                                               Background (fire & forget)
                                                       |
                                            +----------+-----------+
                                            |                      |
                                            v                      v
                                  Resume Tailor Branch    LinkedIn Search Branch
                                  (4 agent calls)         (5-6 agent calls)
                                  Only if default          Always runs
                                  resume is set
```

The two branches run concurrently via `asyncio.gather`. The user sees "Saved to DB!" immediately -- no waiting for downstream agents.

### Resume Tailor Pipeline (4 agent calls)

Triggered automatically by the master pipeline, or manually from the AI workspace on any job.

```
  +-----------+     +-----------+     +-----------+     +-------------+     +---------+
  | JD        |---->| RAG       |---->| Gap       |---->| Suggestions |---->| Rewrite |
  | Analysis  |     | Retrieval |     | Analysis  |     |             |     |         |
  | (agent #1)|     | (ChromaDB)|     | (agent #2)|     | (agent #3)  |     |(agent #4)|
  +-----------+     +-----------+     +-----------+     +-------------+     +---------+
```

Each node produces structured output (Pydantic models). State flows forward: JD analysis feeds gap analysis, which feeds suggestions, which feeds the rewrite. RAG retrieval searches the ChromaDB vector store for relevant experience across all uploaded resume versions.

### Follow-up Refinement (2-5 agent calls)

When the user sends a follow-up message ("emphasize leadership more", "I also have Kafka experience"):

```
  User message -----> Classifier Agent -----> Sets flags -----> Pipeline re-runs
                      (agent call #1)         needs_jd?         only flagged steps
                      Routes to correct       needs_gap?         (1-4 agent calls)
                      pipeline entry point    needs_suggestions?
                      + generates ack msg     needs_rewrite?
```

The classifier generates a natural-language acknowledgement ("Got it, I'll refresh suggestions with more leadership emphasis") that renders immediately while the pipeline re-runs in the background.

### LinkedIn Search Pipeline (5-6 agent calls)

Triggered automatically by the master pipeline, or manually from the LinkedIn Search tab on any job.

```
  +-----------+    +----------+    +-----------+    +-----------+    +-----------+    +----------+
  | Analyze   |--->| Extract  |--->| Web Search|--->| Score     |--->| Generate  |--->| Compile  |
  | JD        |    | Domain   |    | (Brave or |    | Relevance |    | Connection|    | Company  |
  | (agent #1)|    | (agent #2)|    | Google)   |    | (agent #3)|    | Notes     |    | Summary  |
  +-----------+    +----------+    +-----+-----+    +-----------+    | (agent #4)|    | (agent #5)|
                                        |                           +-----------+    +----------+
                                   5 parallel queries:                    |
                                   recruiter, TA,                  Optional: review
                                   hiring mgr, HR,                 leadership results
                                   dept. leadership                + retry (agent #6)
```

Apollo enrichment (company data, tech stack, funding) runs between domain extraction and web search if an API key is configured -- direct API call, no agent needed.

### Mock Interview System (2 + 3N agent/API calls)

Standalone system, not part of the master pipeline. Driven by WebSocket with push-to-talk audio.

```
  +-----------+                    +-----------+
  | Planning  |-- - - - - - - - -->| Scoring   |
  | (agent #1)|                    | (agent #2)|
  +-----+-----+                    +-----+-----+
        |                                ^
        v          Per turn (x N):       |
  +-----------+    +-----+  +-------+  +-----+
  | Opening   |    | STT |->| Turn  |->| TTS |  x N turns
  | question  |    | API |  | Agent |  | API |
  +-----------+    +-----+  +-------+  +-----+
                   Whisper   Processes  Speech
                             response   synthesis
                             + generates
                             next question
```

Planning generates the interview plan and opening question. Each turn: Whisper transcribes the audio (API call), the turn agent processes the response and generates the next question (agent call), TTS synthesizes the reply (API call). All streaming over a single WebSocket. After the interview ends, scoring evaluates the full transcript across five dimensions with cited evidence.

## Agent call summary

| Workflow | Agent calls | API calls | When |
|----------|-------------|-----------|------|
| **Full master pipeline** | **10-12** | **0** | **One-click extension save** |
| -- Extraction | 1-2 | 0 | LLM parses fields + optional retry |
| -- Resume branch | 4 | 0 | Auto if default resume set |
| -- LinkedIn branch | 5-6 | 0 | Auto for every save |
| Resume tailor (manual) | 4 | 0 | User clicks "Analyze" in workspace |
| Follow-up refinement | 2-5 | 0 | User sends message to refine |
| LinkedIn search (manual) | 5-6 | 0 | User opens LinkedIn tab |
| Mock interview | 2 + 1/turn | 2/turn | Planning + N turns + scoring |

Agent call = LLM invocation with dedicated role, system prompt, and structured output schema.
API call = external service (Whisper STT, OpenAI TTS) without agent behavior.

## Setup

```bash
# Install dependencies
npm install
cd backend && uv sync && uv run playwright install chromium && cd ..

# Initialize the database
npx drizzle-kit push

# Start everything (Next.js + FastAPI + ChromaDB)
npm run dev
```

Opens at [http://localhost:3000](http://localhost:3000). Add at least one LLM API key in Settings > API Keys.

### Chrome extension

1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click "Load unpacked" and select the `chrome-extension/` folder
4. The extension defaults to `http://localhost:3000` -- change in the extension popup if needed

### Environment

Optional: copy `backend/.env.example` to `backend/.env` to enable LangSmith tracing.

Data lives in `jobtracker.db` (project root) and `data/` (uploads, extractions, configs). Back them up if they matter.

## Tech stack

| Layer | Tech |
|-------|------|
| **Frontend** | Next.js 16, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| **Frontend DB** | SQLite via libsql + Drizzle ORM (fully async) |
| **Backend** | Python 3.12, FastAPI, LangChain, LangGraph |
| **Backend DB** | SQLite via aiosqlite (fully async) |
| **Vector store** | ChromaDB (resume RAG) |
| **Audio** | OpenAI Whisper (STT), OpenAI TTS (speech synthesis) |
| **Web search** | Brave Search API or Google via Playwright |
| **Company data** | Apollo API (optional enrichment) |
| **LLM providers** | OpenAI, Anthropic, Kimi, OpenRouter, OpenAI Codex |

## Testing

```bash
# Frontend (100 tests)
npx vitest run

# Backend (291 tests)
cd backend && uv run pytest tests/
```

## Project structure

```
JobTracker/
  src/                          # Next.js frontend
    app/                        #   Pages: applications, analytics, resumes, settings
    components/                 #   UI components (40+)
    db/                         #   Drizzle schema + async libsql client
    __tests__/                  #   20 test files, 100 tests
  backend/
    src/
      agents/                   #   LangGraph pipelines + interview engine
        orchestrator.py         #     Resume tailor pipeline (4 nodes)
        master_workflow.py      #     Extension pipeline (extraction + fan-out)
        extraction_pipeline.py  #     LinkedIn job extraction with retry
        linkedin_pipeline.py    #     Contact discovery pipeline (14 steps)
        interview_engine.py     #     Planning, turn processing, scoring
        audio_pipeline.py       #     STT + TTS with streaming
        classifier.py           #     Follow-up routing classifier
      api/                      #   FastAPI routes + WebSocket handler
      models/                   #   Provider registry + role-based config
      memory/                   #   RAG (ChromaDB), conversation history, reindex
      services/                 #   Text extraction, embeddings
    tests/                      #   291 tests
  chrome-extension/             # Chrome extension (content script + popup)
  data/                         # Uploads, extractions, configs (gitignored)
```
