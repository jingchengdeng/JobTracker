"use client";

import { useEffect, useState, useCallback } from "react";
import { Play, Check, Loader2, Copy, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Job, Resume } from "@/lib/types";

interface ResumeTailorTabProps {
  job: Job;
}

interface StepData {
  step_type: string;
  status: string;
  result: string | null;
}

interface RunData {
  id: number;
  status: string;
  error: string | null;
  steps: StepData[];
}

const STEP_LABELS: Record<string, string> = {
  jd_analysis: "JD Analysis",
  gap_analysis: "Gap Analysis",
  suggestions: "Suggestions",
  rewrite: "Rewrite",
};

export function ResumeTailorTab({ job }: ResumeTailorTabProps) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [run, setRun] = useState<RunData | null>(null);
  const [messages, setMessages] = useState<Array<{ role: string; content: string }>>([]);
  const [chatInput, setChatInput] = useState("");
  const [polling, setPolling] = useState(false);

  const fetchResumes = useCallback(async () => {
    try {
      const res = await fetch("/api/resumes");
      if (res.ok) {
        const data = await res.json();
        setResumes(data);
        if (data.length > 0 && !selectedResumeId) {
          setSelectedResumeId(data[0].id);
        }
      }
    } catch (err) {
      console.error(err);
    }
  }, [selectedResumeId]);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

  useEffect(() => {
    if (!run || !polling) return;
    if (run.status === "completed" || run.status === "failed") {
      setPolling(false);
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/ai/runs/${run.id}`);
        if (res.ok) {
          const data = await res.json();
          setRun(data);
          if (data.status === "completed" || data.status === "failed") {
            setPolling(false);
            const msgRes = await fetch(`/api/ai/runs/${run.id}/messages`);
            if (msgRes.ok) {
              const msgData = await msgRes.json();
              setMessages(msgData.messages);
            }
          }
        }
      } catch (err) {
        console.error(err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [run, polling]);

  async function handleAnalyze() {
    if (!selectedResumeId) return;

    try {
      const res = await fetch("/api/ai/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: job.id, resume_id: selectedResumeId }),
      });
      if (res.ok) {
        const data = await res.json();
        setRun({ id: data.run_id, status: "pending", error: null, steps: [] });
        setPolling(true);
        setMessages([]);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleSendMessage() {
    if (!chatInput.trim() || !run) return;

    const content = chatInput;
    setChatInput("");
    setMessages((prev) => [...prev, { role: "user", content }]);

    try {
      await fetch(`/api/ai/runs/${run.id}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setPolling(true);
    } catch (err) {
      console.error(err);
    }
  }

  function parseResult(result: string | null) {
    if (!result) return null;
    try {
      return JSON.parse(result);
    } catch {
      return result;
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={selectedResumeId || ""}
          onChange={(e) => setSelectedResumeId(Number(e.target.value))}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">Select a resume...</option>
          {resumes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name} {r.version ? `(${r.version})` : ""}
            </option>
          ))}
        </select>
        <Button onClick={handleAnalyze} disabled={!selectedResumeId || polling}>
          <Play className="mr-1.5 h-4 w-4" />
          Analyze
        </Button>
      </div>

      {run && (
        <div className="flex gap-2">
          {["jd_analysis", "gap_analysis", "suggestions", "rewrite"].map((stepType) => {
            const step = run.steps?.find((s) => s.step_type === stepType);
            const status = step?.status || "pending";
            return (
              <div key={stepType} className="flex items-center gap-1.5">
                {status === "completed" && <Check className="h-4 w-4 text-green-500" />}
                {status === "running" && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
                {status === "pending" && <div className="h-4 w-4 rounded-full border" />}
                {status === "failed" && <div className="h-4 w-4 rounded-full bg-destructive" />}
                <span className="text-sm">{STEP_LABELS[stepType]}</span>
              </div>
            );
          })}
        </div>
      )}

      {run?.steps?.map((step) => {
        if (step.status !== "completed" || !step.result) return null;
        const data = parseResult(step.result);
        if (!data) return null;

        return (
          <Card key={step.step_type} className="p-4">
            <h3 className="mb-2 font-medium">{STEP_LABELS[step.step_type]}</h3>

            {step.step_type === "jd_analysis" && (
              <div className="space-y-2 text-sm">
                <p><span className="font-medium">Title:</span> {data.title}</p>
                <p><span className="font-medium">Company:</span> {data.company}</p>
                <div>
                  <span className="font-medium">Key Requirements:</span>
                  <ul className="list-disc pl-4">
                    {data.key_requirements?.map((r: string, i: number) => (
                      <li key={i}>{r}</li>
                    ))}
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
                {data.summary && (
                  <p className="text-sm text-muted-foreground">{data.summary}</p>
                )}
                <div className="text-sm">
                  Match score: <Badge>{data.overall_match_score}%</Badge>
                </div>
                <div className="space-y-1">
                  {data.items.map((item: any, i: number) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      <Badge
                        variant={
                          item.status === "match" ? "default" :
                          item.status === "partial" ? "secondary" : "destructive"
                        }
                        className="mt-0.5 shrink-0"
                      >
                        {item.status}
                      </Badge>
                      <div>
                        <span className="font-medium">{item.requirement}</span>
                        <p className="text-muted-foreground">{item.evidence}</p>
                        {item.rag_suggestion && (
                          <p className="text-blue-500">{item.rag_suggestion}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {step.step_type === "suggestions" && data.items && (
              <div className="space-y-3">
                {data.items.map((item: any, i: number) => (
                  <div key={i} className="rounded border p-3 text-sm">
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
                <div className="flex gap-2 mb-3">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigator.clipboard.writeText(data.rewritten_resume || data)}
                  >
                    <Copy className="mr-1.5 h-3.5 w-3.5" />
                    Copy
                  </Button>
                </div>
                <pre className="whitespace-pre-wrap rounded bg-muted p-3 text-sm">
                  {data.rewritten_resume || data}
                </pre>
                {data.changes_made && (
                  <div className="mt-3 text-sm">
                    <p className="font-medium">Changes made:</p>
                    <ul className="list-disc pl-4 text-muted-foreground">
                      {data.changes_made.map((c: string, i: number) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Card>
        );
      })}

      {run && run.status === "completed" && (
        <Card className="p-4">
          <h3 className="mb-3 font-medium">Refine</h3>

          {messages.length > 0 && (
            <div className="mb-3 space-y-2">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`rounded p-2 text-sm ${
                    msg.role === "user"
                      ? "bg-primary/10 text-foreground"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  <span className="font-medium">
                    {msg.role === "user" ? "You" : "AI"}:
                  </span>{" "}
                  {msg.content}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <Input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="e.g. emphasize leadership experience more..."
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
            />
            <Button
              size="icon"
              onClick={handleSendMessage}
              disabled={!chatInput.trim() || polling}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </Card>
      )}

      {run?.status === "failed" && (
        <Card className="border-destructive p-4">
          <p className="text-sm text-destructive">{run.error || "Pipeline failed"}</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={async () => {
              await fetch(`/api/ai/runs/${run.id}/retry`, { method: "POST" });
              setPolling(true);
            }}
          >
            Retry
          </Button>
        </Card>
      )}
    </div>
  );
}
