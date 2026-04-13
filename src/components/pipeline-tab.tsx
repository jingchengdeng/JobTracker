"use client";

import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import type { Job } from "@/lib/types";
import { PipelineDiagram } from "./pipeline-diagram";
import { useTopology } from "@/lib/pipeline-topology-hook";
import type { NodeState, NodeStateMap } from "@/lib/pipeline-layout";

type SnapshotNode = {
  graph: string;
  node_name: string;
  status: NodeState["status"];
  attempt: number;
  workflow_run_id: string;
  version: number;
  round_number: number;
  duration_ms: number | null;
  error: string | null;
  traceback: string | null;
  started_at: string | null;
  completed_at: string | null;
};

type Snapshot = {
  active_runs: Record<"master" | "resume" | "linkedin", string | null>;
  nodes: SnapshotNode[];
};

type StreamFrame =
  | { type: "snapshot"; active_runs: Snapshot["active_runs"]; nodes: SnapshotNode[] }
  | {
      type: "event";
      graph: string;
      workflow_run_id: string;
      node_name: string;
      status: NodeState["status"];
      attempt: number;
      version: number;
      round_number: number;
      duration_ms: number | null;
      error: string | null;
      traceback: string | null;
      job_id: number | null;
    }
  | { type: "graph_reset"; graph: string; workflow_run_id: string };

function nodeKey(f: {
  workflow_run_id: string;
  graph: string;
  node_name: string;
  round_number: number;
  version: number;
}): string {
  return `${f.workflow_run_id}:${f.graph}:${f.node_name}:${f.round_number}:${f.version}`;
}

function snapshotToMap(snap: Snapshot): NodeStateMap {
  const m: NodeStateMap = new Map();
  for (const n of snap.nodes) {
    m.set(
      nodeKey({
        workflow_run_id: n.workflow_run_id,
        graph: n.graph,
        node_name: n.node_name,
        round_number: n.round_number,
        version: n.version,
      }),
      {
        status: n.status,
        attempt: n.attempt,
        durationMs: n.duration_ms,
        error: n.error,
        traceback: n.traceback,
        startedAt: n.started_at,
        completedAt: n.completed_at,
        workflowRunId: n.workflow_run_id,
        version: n.version,
      },
    );
  }
  return m;
}

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(err: unknown) {
    console.error("PipelineTab render error:", err);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 text-sm text-red-300">
          Pipeline diagram crashed. Check the console for details.
        </div>
      );
    }
    return this.props.children;
  }
}

export function PipelineTab({ job }: { job: Job }) {
  const { data: topology, error: topologyError, retry } = useTopology();
  const [states, setStates] = useState<NodeStateMap>(new Map());
  const activeRunsRef = useRef<Snapshot["active_runs"]>({ master: null, resume: null, linkedin: null });

  useEffect(() => {
    const fetchSnapshot = async () => {
      const resp = await fetch(`/api/ai/pipeline/current?job_id=${job.id}`);
      if (!resp.ok) return;
      const snap = (await resp.json()) as Snapshot;
      activeRunsRef.current = snap.active_runs;
      setStates(snapshotToMap(snap));
    };

    fetchSnapshot();
    const es = new EventSource(`/api/ai/pipeline/stream?job_id=${job.id}`);
    es.onopen = () => {
      fetchSnapshot();
    };
    es.onmessage = (ev) => {
      const frame = JSON.parse(ev.data) as StreamFrame;
      setStates((prev) => {
        const next = new Map(prev);
        if (frame.type === "snapshot") {
          activeRunsRef.current = frame.active_runs;
          next.clear();
          for (const n of frame.nodes) {
            next.set(
              nodeKey({
                workflow_run_id: n.workflow_run_id,
                graph: n.graph,
                node_name: n.node_name,
                round_number: n.round_number,
                version: n.version,
              }),
              {
                status: n.status,
                attempt: n.attempt,
                durationMs: n.duration_ms,
                error: n.error,
                traceback: n.traceback,
                startedAt: n.started_at,
                completedAt: n.completed_at,
                workflowRunId: n.workflow_run_id,
                version: n.version,
              },
            );
          }
          return next;
        }
        if (frame.type === "graph_reset") {
          const g = frame.graph as keyof typeof activeRunsRef.current;
          const oldWf = activeRunsRef.current[g];
          if (oldWf) {
            for (const k of Array.from(next.keys())) {
              if (k.startsWith(`${oldWf}:${g}:`)) next.delete(k);
            }
          }
          activeRunsRef.current = { ...activeRunsRef.current, [g]: frame.workflow_run_id };
          return next;
        }
        next.set(
          nodeKey({
            workflow_run_id: frame.workflow_run_id,
            graph: frame.graph,
            node_name: frame.node_name,
            round_number: frame.round_number,
            version: frame.version,
          }),
          {
            status: frame.status,
            attempt: frame.attempt,
            durationMs: frame.duration_ms,
            error: frame.error,
            traceback: frame.traceback,
            startedAt: null,
            completedAt: null,
            workflowRunId: frame.workflow_run_id,
            version: frame.version,
          },
        );
        return next;
      });
    };
    return () => {
      es.close();
    };
  }, [job.id]);

  if (topologyError) {
    return (
      <div className="flex h-[640px] flex-col items-center justify-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] text-sm text-red-300">
        <p>Failed to load pipeline topology: {topologyError.message}</p>
        <button
          onClick={retry}
          className="rounded border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-slate-200 hover:bg-white/[0.08]"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!topology) {
    return (
      <div className="flex h-[640px] items-center justify-center rounded-xl border border-white/[0.06] bg-white/[0.02] text-sm text-slate-400">
        Loading pipeline topology…
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl">
        <PipelineDiagram topology={topology} nodeStates={states} />
      </div>
    </ErrorBoundary>
  );
}
