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

- **API Keys** — configure keys for OpenAI, Anthropic, Kimi, or OpenRouter. OpenAI Codex is supported via OAuth login.
- **Models** — role-based model config: pick which model handles classification, which runs the agent pipeline, and which generates embeddings. Each role can use a different provider.
- **Preferences** — personal context (years of experience, target roles, tone) that guides AI output.

### Demo Tabs

- **LinkedIn Search** — mock company overview and suggested connections with templated outreach messages.
- **Mock Interview** — sample interview setup and feedback scores to preview a future feature.

## Setup

```bash
npm install
cd backend && uv sync && cd ..
npx drizzle-kit push
npm run dev
```

This starts both the Next.js frontend (port 3000) and the Python backend (port 8000) together via `concurrently`. Open [http://localhost:3000](http://localhost:3000).

You'll need at least one LLM API key to use the AI features. Add it in Settings > API Keys after starting the app.

Optional: copy `backend/.env.example` to `backend/.env` to enable LangSmith tracing.

Your data lives in `jobtracker.db` in the project root and uploaded files go to `data/`. Back them up if they matter to you.

## Tech

**Frontend:** Next.js 15, TypeScript, Tailwind, shadcn/ui, SQLite (via Drizzle), Recharts.

**Backend:** Python 3.12, FastAPI, LangChain, LangGraph, ChromaDB, PyMuPDF, python-docx.

**LLM Providers:** OpenAI, Anthropic, Kimi, OpenRouter, OpenAI Codex (OAuth).

## Testing

```bash
# frontend
npx vitest run

# backend
cd backend && uv run pytest tests/
```
