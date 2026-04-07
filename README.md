# JobTracker

A local dashboard for tracking job applications, with AI-powered resume tailoring. Built because spreadsheets get messy fast when you're applying to dozens of places.

## What it does

### Applications & Analytics

- **Applications** — add, edit, search, and filter your job applications. Click any row to see full details in a side panel, then open the AI workspace to tailor your resume for that role.
- **Analytics** — pipeline funnel, applications over time, source breakdown, and salary distribution. Set weekly or monthly goals to keep yourself on track.

### AI Resume Tailoring

Open the AI workspace from any job to get help matching your resume to the posting.

- **Resume Tailor** — select a resume, hit Analyze, and a four-step pipeline runs: JD analysis, gap analysis, suggestions, and a full rewrite. Send follow-up messages to refine the results — the classifier decides which steps to re-run, writes a natural-language acknowledgement, and only updates what changed.
- **Conversation log** — each follow-up renders as its own round with your message, the AI response, and collapsible step cards. Older rounds auto-collapse. The composer stays pinned at the bottom so you can always type.
- **RAG** — uploaded resumes are chunked and indexed in ChromaDB. The pipeline searches your resume corpus to pull in relevant context for suggestions and rewrites.

### Resume Management

- **Resumes** — upload and manage resumes (PDF or DOCX). Text is extracted automatically. Embedding status badges show which resumes are indexed and which need reindexing after a model change.

### Settings

- **API Keys** — configure keys for OpenAI, Anthropic, Kimi, OpenRouter, or Apollo. OpenAI Codex is supported via OAuth login. Apollo is optional and enables company enrichment in LinkedIn Search.
- **Models** — role-based model config: pick which model handles classification, which runs the agent pipeline, which generates embeddings, which powers interviews, and which runs LinkedIn search. Each role can use a different provider.
- **Preferences** — personal context (years of experience, target roles, tone) that guides AI output.

### Mock Interview

Practice for real interviews with an AI interviewer that adapts to the job description and your resume.

- **Interview types** — technical, behavioral, or system design. Choose difficulty, duration (15–60 min), and focus area.
- **Voice & text** — hold Space to speak (push-to-talk), or type answers as a fallback. The interviewer responds with text and synthesized audio.
- **Realistic conversation** — the AI asks one question at a time, probes deeper on vague answers, and moves on when you've demonstrated understanding.
- **Scoring** — five fixed dimensions per interview type, each scored 0–10 with specific evidence cited from the transcript. Overall score out of 50.
- **Results** — tabbed view with score breakdown, per-dimension feedback with evidence citations, and full transcript.
- **Session history** — past sessions appear in a sidebar. Click to review, or delete with one click.

Requires an OpenAI key (for speech-to-text and text-to-speech) and an LLM key for the interviewer model.

### LinkedIn Search

Open the AI workspace from any job and switch to the LinkedIn Search tab.

- **Company Enrichment** — if you add an Apollo API key in Settings, the pipeline fetches company data (size, funding, tech stack, department breakdown) and generates an interview-prep summary.
- **Contact Discovery** — searches Google for recruiters, talent acquisition, HR, hiring managers, and department peers at the target company. No API key or LinkedIn login needed.
- **Relevance Scoring** — each contact is scored 0-100 based on how relevant they are to your specific job posting.
- **Connection Notes** — generates a personalized 300-character LinkedIn connection note per contact with a copy button.

## Setup

```bash
npm install
cd backend && uv sync && uv run playwright install chromium && cd ..
npx drizzle-kit push
npm run dev
```

This starts both the Next.js frontend (port 3000) and the Python backend (port 8000) together via `concurrently`. Open [http://localhost:3000](http://localhost:3000).

You'll need at least one LLM API key to use the AI features. Add it in Settings > API Keys after starting the app.

Optional: copy `backend/.env.example` to `backend/.env` to enable LangSmith tracing.

Your data lives in `jobtracker.db` in the project root and uploaded files go to `data/`. Back them up if they matter to you.

## Tech

**Frontend:** Next.js 15, TypeScript, Tailwind, shadcn/ui, SQLite (via Drizzle), Recharts.

**Backend:** Python 3.12, FastAPI, LangChain, LangGraph, ChromaDB, PyMuPDF, python-docx, Playwright. WebSocket for real-time interview audio streaming.

**LLM Providers:** OpenAI, Anthropic, Kimi, OpenRouter, OpenAI Codex (OAuth).

## Testing

```bash
# frontend
npx vitest run

# backend
cd backend && uv run pytest tests/
```
