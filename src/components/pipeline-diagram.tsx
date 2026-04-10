"use client";

import { useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { buildTopology } from "./pipeline-topology";
import { PipelineErrorModal } from "./pipeline-error-modal";
import { cn } from "@/lib/utils";

export type NodeState = {
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  attempt: number;
  durationMs: number | null;
  error: string | null;
  traceback: string | null;
  startedAt: string | null;
  completedAt: string | null;
  workflowRunId: string;
};

export type NodeStateMap = Map<string, NodeState>;

const STATUS_COLORS = {
  pending: "bg-slate-500/20 border-slate-400/40 text-slate-300",
  running: "bg-blue-500/20 border-blue-400 text-blue-200 shadow-[0_0_12px_rgba(59,130,246,0.4)]",
  completed: "bg-green-500/20 border-green-400/60 text-green-200",
  failed: "bg-red-500/20 border-red-400 text-red-200 shadow-[0_0_12px_rgba(239,68,68,0.5)]",
  skipped: "border-dashed border-slate-500/40 bg-transparent text-slate-500",
} as const;

function PipelineNodeComponent({ data }: NodeProps) {
  const label = data.label as string;
  const state = data.state as NodeState | undefined;
  const status = state?.status ?? "pending";
  const attempt = state?.attempt ?? 0;

  const tooltipBody = state
    ? state.status === "failed"
      ? `Failed: ${state.error ?? "unknown error"}`
      : `${state.status} · ${state.durationMs ?? "—"}ms`
    : "pending";

  return (
    <TooltipProvider delay={100}>
      <Tooltip>
        <TooltipTrigger
          render={
            <div
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium cursor-pointer select-none",
                STATUS_COLORS[status],
              )}
            />
          }
        >
          <div className="flex items-center gap-1.5">
            {label}
            {attempt > 1 && (
              <span className="rounded bg-white/10 px-1 text-[9px]">
                {attempt}/{attempt}
              </span>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>{tooltipBody}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

const nodeTypes = { pipelineNode: PipelineNodeComponent };

type Props = {
  nodeStates: NodeStateMap;
};

export function PipelineDiagram({ nodeStates }: Props) {
  const [modalNode, setModalNode] = useState<{ key: string; state: NodeState } | null>(null);

  const { nodes: baseNodes, edges } = useMemo(() => buildTopology(), []);

  const nodes: Node[] = useMemo(() => {
    return baseNodes.map((n) => {
      if (n.type !== "pipelineNode") return n;
      const nodeKey = `${n.data.graph}:${n.data.nodeName}`;
      const state = findLatest(nodeStates, nodeKey);
      return { ...n, data: { ...n.data, state } };
    });
  }, [baseNodes, nodeStates]);

  const onNodeClick = useCallback(
    (_e: React.MouseEvent, node: Node) => {
      const nodeKey = `${node.data.graph}:${node.data.nodeName}`;
      const state = findLatest(nodeStates, nodeKey);
      if (state?.status === "failed") {
        setModalNode({ key: nodeKey, state });
      }
    },
    [nodeStates],
  );

  return (
    <div className="h-[600px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
      >
        <Background color="#ffffff08" gap={22} />
        <Controls />
      </ReactFlow>

      {modalNode && (
        <PipelineErrorModal
          open
          onClose={() => setModalNode(null)}
          nodeName={modalNode.key.split(":")[1]}
          graph={modalNode.key.split(":")[0]}
          attempt={modalNode.state.attempt}
          maxAttempts={modalNode.state.attempt}
          durationMs={modalNode.state.durationMs}
          startedAt={modalNode.state.startedAt}
          error={modalNode.state.error ?? "unknown error"}
          traceback={modalNode.state.traceback}
        />
      )}
    </div>
  );
}

function findLatest(map: NodeStateMap, topoKey: string): NodeState | undefined {
  let latest: NodeState | undefined;
  let latestStart: string | null = null;
  for (const [k, v] of map.entries()) {
    if (!k.includes(topoKey)) continue;
    if (!latestStart || (v.startedAt && v.startedAt > latestStart)) {
      latest = v;
      latestStart = v.startedAt;
    }
  }
  return latest;
}
