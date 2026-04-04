# JobTracker

A local dashboard for tracking job applications, with AI-powered resume tailoring. Built because spreadsheets get messy fast when you're applying to dozens of places.

## What it does

- **Applications tab** — add, edit, search, and filter your job applications. Click any row to see full details in a side panel.
- **Analytics tab** — see where your applications stand with charts for your pipeline funnel, applications over time, source breakdown, and salary distribution. Set weekly or monthly goals to keep yourself on track.
- **AI Assistant** — open from any job to get AI help tailoring your resume. Select a resume, hit Analyze, and the pipeline runs through JD analysis, gap analysis, suggestions, and a full rewrite. Send follow-up messages to refine the results.
- **Resumes tab** — upload and manage your resumes (PDF or DOCX). Text is extracted automatically for use by the AI pipeline.
- **Settings tab** — configure API keys (OpenAI, Anthropic, or OpenRouter), choose which models to use, and set personal preferences that guide the AI output.
- **LinkedIn Search** (demo) — mock company overview and suggested connections with templated outreach messages.
- **Mock Interview** (demo) — sample interview setup and feedback scores to preview a future feature.

## Setup

```bash
npm install
cd backend && uv sync && cd ..
npx drizzle-kit push
npm run dev
```

This starts both the Next.js frontend (port 3000) and the Python backend (port 8000) together via `concurrently`. Open [http://localhost:3000](http://localhost:3000).

You'll need at least one LLM API key to use the AI features. Add it in Settings > API Keys after starting the app. Supported providers: OpenAI, Anthropic, OpenRouter.

Your data lives in `jobtracker.db` in the project root and uploaded files go to `data/`. Back them up if they matter to you.

## Tech

**Frontend:** Next.js, TypeScript, Tailwind, base-ui, SQLite (via Drizzle), Recharts.

**Backend:** Python, FastAPI, LangChain, LangGraph, ChromaDB, PyMuPDF, python-docx.
