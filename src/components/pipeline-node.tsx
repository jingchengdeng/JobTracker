"use client";

import { memo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { NodeState } from "@/lib/pipeline-layout";
import { cn } from "@/lib/utils";

type PipelineNodeData = {
  label: string;
  graph: string;
  nodeName: string;
  state?: NodeState;
  onFailedClick?: () => void;
};

const STATUS_STYLES = {
  pending: {
    header: "bg-slate-500/15 text-slate-400",
    card: "border-white/[0.06]",
  },
  running: {
    header: "bg-blue-500/25 text-blue-200",
    card: "border-blue-400/40 shadow-[0_0_20px_rgba(59,130,246,0.3)]",
  },
  completed: {
    header: "bg-emerald-500/25 text-emerald-200",
    card: "border-emerald-400/30",
  },
  failed: {
    header: "bg-red-500/30 text-red-200",
    card: "border-red-400/60 shadow-[0_0_20px_rgba(239,68,68,0.4)] cursor-pointer",
  },
  skipped: {
    header: "bg-transparent text-slate-500 border-b border-dashed border-slate-500/30",
    card: "border-dashed border-slate-500/30 opacity-50",
  },
} as const;

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

type PipelineNodeProps = Omit<
  NodeProps<Node<PipelineNodeData>>,
  "selectable" | "deletable" | "draggable" | "positionAbsoluteX" | "positionAbsoluteY"
> & {
  selectable?: boolean;
  deletable?: boolean;
  draggable?: boolean;
  positionAbsoluteX?: number;
  positionAbsoluteY?: number;
  xPos?: number;
  yPos?: number;
};

function PipelineNodeInner(props: PipelineNodeProps) {
  const data = props.data;
  const state = data.state;
  const status = state?.status ?? "pending";
  const styles = STATUS_STYLES[status];

  const handleClick = () => {
    if (status === "failed" && data.onFailedClick) data.onFailedClick();
  };

  return (
    <div
      data-testid="pipeline-node-card"
      onClick={handleClick}
      className={cn(
        "flex h-[52px] w-[180px] flex-col overflow-hidden rounded-lg border bg-white/[0.03] backdrop-blur-md",
        styles.card,
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
      <Handle
        id="target-left"
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
      <Handle
        id="target-right"
        type="target"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
      <div
        className={cn(
          "flex items-center justify-between px-2 py-0.5 text-[9px] uppercase tracking-wide font-semibold",
          styles.header,
        )}
      >
        <span>{data.graph}</span>
        <div className="flex items-center gap-1">
          <span>{status}</span>
          {state && state.attempt > 1 && (
            <span className="rounded bg-white/10 px-1 text-[8px] font-mono">
              ×{state.attempt}
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-1 items-center justify-between gap-1 px-2 text-[11px] font-mono text-slate-200">
        <span className="truncate">{data.label}</span>
        {state?.durationMs != null && (
          <span className="shrink-0 rounded bg-white/[0.06] px-1 py-0.5 text-[9px] text-slate-400">
            {formatMs(state.durationMs)}
          </span>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
      <Handle
        id="source-left"
        type="source"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
      <Handle
        id="source-right"
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-0 !bg-white/30"
      />
    </div>
  );
}

export const PipelineNode = memo(PipelineNodeInner);
