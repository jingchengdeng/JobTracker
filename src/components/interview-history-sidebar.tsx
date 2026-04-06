"use client";

import { Badge } from "@/components/ui/badge";
import type { InterviewSessionSummary } from "@/lib/types";

interface Props {
  sessions: InterviewSessionSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function InterviewHistorySidebar({ sessions, selectedId, onSelect }: Props) {
  if (sessions.length === 0) return null;

  return (
    <div className="w-48 shrink-0 space-y-1 border-r pr-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Past Sessions</p>
      {sessions.map((s) => (
        <button
          key={s.id}
          onClick={() => onSelect(s.id)}
          className={`w-full rounded px-2 py-1.5 text-left text-xs ${
            selectedId === s.id ? "bg-muted" : "hover:bg-muted/50"
          }`}
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
      ))}
    </div>
  );
}
