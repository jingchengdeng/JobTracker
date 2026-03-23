# JobTracker

A local dashboard for tracking job applications. Built because spreadsheets get messy fast when you're applying to dozens of places.

## What it does

- **Applications tab** — add, edit, search, and filter your job applications. Click any row to see full details in a side panel.
- **Analytics tab** — see where your applications stand with charts for your pipeline funnel, applications over time, source breakdown, and salary distribution. Set weekly or monthly goals to keep yourself on track.

## Setup

```bash
npm install
npx drizzle-kit push
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Your data lives in `jobtracker.db` in the project root. Back it up if it matters to you.

## Tech

Next.js, Tailwind, shadcn/ui, SQLite (via Drizzle), Recharts.
