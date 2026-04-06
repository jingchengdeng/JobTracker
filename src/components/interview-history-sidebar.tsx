"use client";

import { Badge } from "@/components/ui/badge";
import type { InterviewSessionSummary } from "@/lib/types";

interface Props {
  sessions: InterviewSessionSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

export function InterviewHistorySidebar({ sessions, selectedId, onSelect, onDelete }: Props) {
  if (sessions.length === 0) return null;

  return (
    <div className="w-48 shrink-0 space-y-1 border-r pr-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Past Sessions</p>
      {sessions.map((s) => (
        <div
          key={s.id}
          className={`group flex items-center rounded px-2 py-1.5 text-xs ${
            selectedId === s.id ? "bg-muted" : "hover:bg-muted/50"
          }`}
        >
          <button
            onClick={() => onSelect(s.id)}
            className="flex-1 text-left"
          >
            <div className="flex items-center justify-between">
              <span className="capitalize">{s.interview_type.replace("_", " ")}</span>
              {s.overall_score != null && (
                <Badge variant="secondary" className="text-xs">{s.overall_score}</Badge>
              )}
            </div>
            <div className="text-muted-foreground">
              {new Date(s.created_at).toLocaleDateString()}
            </div>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm("Delete this interview session?")) {
                onDelete(s.id);
              }
            }}
            className="ml-1 shrink-0 rounded p-1 text-muted-foreground/50 opacity-0 hover:text-destructive group-hover:opacity-100"
            title="Delete session"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
