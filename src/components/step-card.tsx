"use client";

import { Check, ChevronDown, ChevronRight, Loader2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { StepData } from "@/lib/group-by-round";

const STEP_LABELS: Record<string, string> = {
  jd_analysis: "JD Analysis",
  gap_analysis: "Gap Analysis",
  suggestions: "Suggestions",
  rewrite: "Rewrite",
};

interface StepCardProps {
  step: StepData;
  expanded: boolean;
  onToggle: () => void;
}

function parseResult(result: string | null) {
  if (!result) return null;
  try {
    return JSON.parse(result);
  } catch {
    return result;
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <Check aria-label="completed" className="h-4 w-4 text-green-500" />;
  if (status === "running") return <Loader2 aria-label="running" className="h-4 w-4 animate-spin text-blue-500" />;
  if (status === "failed") return <X aria-label="failed" className="h-4 w-4 text-destructive" />;
  return <span aria-label="pending" className="text-muted-foreground">—</span>;
}

export function StepCard({ step, expanded, onToggle }: StepCardProps) {
  const label = STEP_LABELS[step.step_type] ?? step.step_type;
  const data = expanded ? parseResult(step.result) : null;

  return (
    <Card className="p-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-muted/40"
      >
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <StatusIcon status={step.status} />
        <span className="flex-1 text-sm font-medium">{label}</span>
        {step.status === "failed" && step.result && (
          <span className="text-xs text-destructive">{step.result}</span>
        )}
      </button>
      {expanded && data && (
        <div className="border-t px-4 py-3 text-sm">
          {step.step_type === "jd_analysis" && (
            <div className="space-y-2">
              <p><span className="font-medium">Title:</span> {data.title}</p>
              <p><span className="font-medium">Company:</span> {data.company}</p>
              <div>
                <span className="font-medium">Key Requirements:</span>
                <ul className="list-disc pl-4">
                  {data.key_requirements?.map((r: string, i: number) => <li key={i}>{r}</li>)}
                </ul>
              </div>
              <div>
                <span className="font-medium">Technologies:</span>{" "}
                {data.technologies?.map((t: string, i: number) => (
                  <Badge key={i} variant="secondary" className="mr-1">{t}</Badge>
                ))}
              </div>
            </div>
          )}
          {step.step_type === "gap_analysis" && data.items && (
            <div className="space-y-2">
              {data.summary && <p className="text-muted-foreground">{data.summary}</p>}
              <div>Match score: <Badge>{data.overall_match_score}%</Badge></div>
              <div className="space-y-1">
                {data.items.map((item: { status: string; requirement: string; evidence: string; rag_suggestion?: string }, i: number) => (
                  <div key={i} className="flex items-start gap-2">
                    <Badge
                      variant={item.status === "match" ? "default" : item.status === "partial" ? "secondary" : "destructive"}
                      className="mt-0.5 shrink-0"
                    >
                      {item.status}
                    </Badge>
                    <div>
                      <span className="font-medium">{item.requirement}</span>
                      <p className="text-muted-foreground">{item.evidence}</p>
                      {item.rag_suggestion && <p className="text-blue-500">{item.rag_suggestion}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {step.step_type === "suggestions" && data.items && (
            <div className="space-y-3">
              {data.items.map((item: { section: string; current: string; suggested: string; reasoning: string }, i: number) => (
                <div key={i} className="rounded border p-3">
                  <p className="font-medium">{item.section}</p>
                  <p className="text-muted-foreground">Current: {item.current}</p>
                  <p className="text-green-600 dark:text-green-400">Suggested: {item.suggested}</p>
                  <p className="text-xs text-muted-foreground">{item.reasoning}</p>
                </div>
              ))}
            </div>
          )}
          {step.step_type === "rewrite" && (
            <div>
              <pre className="whitespace-pre-wrap rounded bg-muted p-3">
                {typeof data === "string" ? data : data.rewritten_resume}
              </pre>
              {data.changes_made && (
                <div className="mt-3">
                  <p className="font-medium">Changes made:</p>
                  <ul className="list-disc pl-4 text-muted-foreground">
                    {data.changes_made.map((c: string, i: number) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
