"use client";

import { Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { RunSummary } from "@/lib/types";

interface Props {
  runs: RunSummary[];
  selectedRunId: number | null;
  onSelect: (runId: number) => void;
  onDelete: (runId: number) => void;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function statusBadge(status: RunSummary["status"]) {
  if (status === "running")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-blue-600">
        <Loader2 className="h-3 w-3 animate-spin" /> running
      </span>
    );
  if (status === "failed")
    return <Badge variant="destructive" className="text-xs">failed</Badge>;
  if (status === "pending")
    return <Badge variant="secondary" className="text-xs">pending</Badge>;
  return <Badge variant="default" className="text-xs">completed</Badge>;
}

export function RunHistorySidebar({ runs, selectedRunId, onSelect, onDelete }: Props) {
  if (runs.length === 0) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        No analyses yet. Click New Analysis to start.
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {runs.map((r) => {
        const selected = r.id === selectedRunId;
        const label = `${r.resume_name}${r.resume_version ? ` · ${r.resume_version}` : ""}`;
        return (
          <li key={r.id} className="relative">
            <button
              type="button"
              onClick={() => onSelect(r.id)}
              aria-label={label}
              className={`w-full rounded p-2 text-left text-sm hover:bg-muted ${
                selected ? "border-l-2 border-primary bg-muted" : ""
              }`}
            >
              <div className="font-medium truncate pr-8">
                {r.resume_name}
                {r.resume_version && <span> · {r.resume_version}</span>}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                <span>{relativeTime(r.created_at)}</span>
                <span>·</span>
                <span>{r.match_score !== null ? `${r.match_score}%` : "—"}</span>
              </div>
              <div className="mt-1">{statusBadge(r.status)}</div>
            </button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Delete run"
              disabled={r.status === "running"}
              className="absolute right-1 top-1 h-7 w-7"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(r.id);
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
