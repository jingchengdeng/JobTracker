"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Play, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { RunHistorySidebar } from "@/components/run-history-sidebar";
import { RoundBlock } from "@/components/round-block";
import { useRunHistory } from "@/hooks/use-run-history";
import { groupByRound, type Message, type StepData } from "@/lib/group-by-round";
import type { Job, Resume } from "@/lib/types";

interface ResumeTailorTabProps {
  job: Job;
}

interface RunData {
  id: number;
  status: string;
  error: string | null;
  steps: StepData[];
}

const POLL_INTERVAL_MS = 2000;

export function ResumeTailorTab({ job }: ResumeTailorTabProps) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [activeRun, setActiveRun] = useState<RunData | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [expandedStepIds, setExpandedStepIds] = useState<Set<number>>(new Set());
  const lastRoundRef = useRef<number>(-1);
  const lastFetchedMsgRoundRef = useRef<number>(-1);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const { runs, error: runsError, refresh: refreshRuns } = useRunHistory(job.id);

  const rounds = useMemo(
    () => groupByRound(activeRun?.steps ?? [], messages),
    [activeRun?.steps, messages],
  );

  const fetchResumes = useCallback(async () => {
    try {
      const res = await fetch("/api/resumes");
      if (res.ok) {
        const data = await res.json();
        setResumes(data);
        setSelectedResumeId((prev) => prev ?? (data.length > 0 ? data[0].id : null));
      }
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { fetchResumes(); }, [fetchResumes]);

  useEffect(() => {
    if (selectedRunId === null && runs.length > 0) setSelectedRunId(runs[0].id);
    if (runs.length === 0 && selectedRunId !== null) setSelectedRunId(null);
  }, [runs, selectedRunId]);

  useEffect(() => {
    lastRoundRef.current = -1;
    lastFetchedMsgRoundRef.current = -1;
    if (selectedRunId === null) {
      setActiveRun(null);
      setMessages([]);
      setExpandedStepIds(new Set());
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const [runRes, msgRes] = await Promise.all([
          fetch(`/api/ai/runs/${selectedRunId}`),
          fetch(`/api/ai/runs/${selectedRunId}/messages`),
        ]);
        if (cancelled) return;
        if (runRes.status === 404) {
          setSelectedRunId(null);
          refreshRuns();
          return;
        }
        if (runRes.ok) {
          const runData: RunData = await runRes.json();
          setActiveRun(runData);
          const maxR = runData.steps?.length
            ? Math.max(...runData.steps.map((s) => s.round_number))
            : -1;
          lastFetchedMsgRoundRef.current = maxR;
        }
        if (msgRes.ok) {
          const data = await msgRes.json();
          setMessages(data.messages);
        }
      } catch (err) { console.error(err); }
    }
    load();
    return () => { cancelled = true; };
  }, [selectedRunId, refreshRuns]);

  useEffect(() => {
    if (rounds.length === 0) return;
    const latest = rounds[rounds.length - 1];
    if (latest.round_number === lastRoundRef.current) return;
    lastRoundRef.current = latest.round_number;
    setExpandedStepIds(new Set(latest.steps.map((s) => s.id)));
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [rounds]);

  useEffect(() => {
    if (!activeRun) return;
    if (activeRun.status !== "running" && activeRun.status !== "pending") return;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/ai/runs/${activeRun.id}`);
        if (res.ok) setActiveRun(await res.json());
      } catch (err) { console.error(err); }
    }, POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [activeRun]);

  const maxRoundInSteps = useMemo(() => {
    if (!activeRun?.steps?.length) return -1;
    return Math.max(...activeRun.steps.map((s) => s.round_number));
  }, [activeRun?.steps]);
  useEffect(() => {
    if (!activeRun) return;
    if (maxRoundInSteps < 0) return;
    if (maxRoundInSteps <= lastFetchedMsgRoundRef.current) return;
    lastFetchedMsgRoundRef.current = maxRoundInSteps;
    let cancelled = false;
    fetch(`/api/ai/runs/${activeRun.id}/messages`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (!cancelled && data) setMessages(data.messages); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [activeRun?.id, maxRoundInSteps]);

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
        setSelectedRunId(data.run_id);
        setMessages([]);
        await refreshRuns();
      }
    } catch (err) { console.error(err); }
  }

  async function handleSendMessage() {
    if (!chatInput.trim() || !activeRun) return;
    const content = chatInput;
    setChatInput("");
    try {
      await fetch(`/api/ai/runs/${activeRun.id}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setActiveRun({ ...activeRun, status: "running" });
    } catch (err) { console.error(err); }
  }

  async function handleDelete(runId: number) {
    if (!confirm("Delete this run? Its conversation and results will be removed.")) return;
    try {
      const res = await fetch(`/api/ai/runs/${runId}`, { method: "DELETE" });
      if (res.status === 409) { alert("Wait for the run to finish before deleting."); return; }
      if (!res.ok && res.status !== 204) { alert("Failed to delete run."); return; }
      if (selectedRunId === runId) setSelectedRunId(null);
      await refreshRuns();
    } catch (err) { console.error(err); }
  }

  function toggleStep(stepId: number) {
    setExpandedStepIds((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      return next;
    });
  }

  const polling = activeRun?.status === "running" || activeRun?.status === "pending";

  return (
    <div className="flex gap-4">
      <aside className="w-60 shrink-0 border-r pr-3">
        <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">History</div>
        {runsError ? (
          <div className="p-3 text-sm">
            <p className="text-destructive">Unable to load runs.</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={refreshRuns}>Retry</Button>
          </div>
        ) : (
          <RunHistorySidebar
            runs={runs}
            selectedRunId={selectedRunId}
            onSelect={setSelectedRunId}
            onDelete={handleDelete}
          />
        )}
      </aside>

      <div className="flex-1 flex flex-col gap-4" key={activeRun?.id ?? "empty"}>
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
            <Play className="mr-1.5 h-4 w-4" /> New Analysis
          </Button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto">
          {rounds.map((r) => (
            <RoundBlock
              key={r.round_number}
              round={r}
              expandedStepIds={expandedStepIds}
              onToggleStep={toggleStep}
            />
          ))}

          {activeRun?.status === "failed" && (
            <Card className="border-destructive p-4">
              <p className="text-sm text-destructive">{activeRun.error || "Pipeline failed"}</p>
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={async () => {
                  await fetch(`/api/ai/runs/${activeRun.id}/retry`, { method: "POST" });
                  setActiveRun({ ...activeRun, status: "pending" });
                  refreshRuns();
                }}
              >
                Retry
              </Button>
            </Card>
          )}

          {!activeRun && runs.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Pick a resume and click New Analysis to start.
            </p>
          )}

          <div ref={bottomRef} />
        </div>

        {activeRun && (
          <div className="border-t pt-3">
            <div className="flex gap-2">
              <Input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask for another refine..."
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                disabled={polling}
              />
              <Button
                size="icon"
                onClick={handleSendMessage}
                disabled={!chatInput.trim() || polling}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
