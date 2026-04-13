"use client";

import { useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  layoutGraphs,
  reindex,
  lookupState,
  deriveDisplayStatus,
  type NodeState,
  type NodeStateMap,
  type Topology,
} from "@/lib/pipeline-layout";
import { PipelineNode } from "./pipeline-node";
import { PipelineLegend } from "./pipeline-legend";
import { PipelineErrorModal } from "./pipeline-error-modal";

export type { NodeState, NodeStateMap };

const nodeTypes = { pipelineNode: PipelineNode };

type Props = {
  topology: Topology;
  nodeStates: NodeStateMap;
};

function splitGraphNode(id: string): { graph: string; nodeName: string } | null {
  const firstColon = id.indexOf(":");
  if (firstColon < 0) return null;
  return { graph: id.slice(0, firstColon), nodeName: id.slice(firstColon + 1) };
}

export function PipelineDiagram({ topology, nodeStates }: Props) {
  const [modalNode, setModalNode] = useState<{ graph: string; nodeName: string; state: NodeState } | null>(null);

  const { nodes: baseNodes, edges } = useMemo(() => layoutGraphs(topology), [topology]);
  const index = useMemo(() => reindex(nodeStates), [nodeStates]);

  const nodes: Node[] = useMemo(() => {
    return baseNodes.map((n) => {
      const data = n.data as { graph: string; nodeName: string; label: string };
      const rawState = lookupState(index, data.graph, data.nodeName);
      const displayStatus = deriveDisplayStatus(topology, index, data.graph, data.nodeName);
      // If the node has no backing state but derivation says "skipped", give
      // the renderer a minimal synthetic state so PipelineNode picks the
      // skipped styling instead of falling back to "pending".
      const nodeState: NodeState | undefined =
        rawState ??
        (displayStatus === "skipped"
          ? {
              status: "skipped",
              attempt: 0,
              durationMs: null,
              error: null,
              traceback: null,
              startedAt: null,
              completedAt: null,
              workflowRunId: "",
              version: 0,
            }
          : undefined);
      return {
        ...n,
        data: {
          ...data,
          state: nodeState,
          onFailedClick: () => {
            if (nodeState?.status === "failed") {
              setModalNode({ graph: data.graph, nodeName: data.nodeName, state: nodeState });
            }
          },
        },
      };
    });
  }, [baseNodes, index, topology]);

  const animatedEdges = useMemo(() => {
    return edges.map((e) => {
      const src = splitGraphNode(e.source);
      const tgt = splitGraphNode(e.target);
      if (!src || !tgt) return e;
      const srcState = lookupState(index, src.graph, src.nodeName);
      const tgtState = lookupState(index, tgt.graph, tgt.nodeName);
      const live = srcState?.status === "completed" && tgtState?.status === "running";
      // Fade skipped-branch edges: if either endpoint is derived-skipped, we
      // dim the edge so the active path pops visually.
      const srcDisplay = deriveDisplayStatus(topology, index, src.graph, src.nodeName);
      const tgtDisplay = deriveDisplayStatus(topology, index, tgt.graph, tgt.nodeName);
      const dimmed = srcDisplay === "skipped" || tgtDisplay === "skipped";
      const baseStyle = e.style ?? {};
      return {
        ...e,
        animated: live,
        style: dimmed ? { ...baseStyle, stroke: "rgba(148,163,184,0.2)" } : baseStyle,
      };
    });
  }, [edges, index, topology]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const data = node.data as { graph: string; nodeName: string; state?: NodeState };
    if (data.state?.status === "failed") {
      setModalNode({ graph: data.graph, nodeName: data.nodeName, state: data.state });
    }
  }, []);

  if (topology.error) {
    return (
      <div className="flex h-[640px] items-center justify-center text-sm text-red-300">
        Failed to load pipeline topology: {topology.error}
      </div>
    );
  }

  return (
    <div className="flex h-[640px] w-full flex-col bg-[#0a0820]">
      <PipelineLegend />
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={animatedEdges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          nodesDraggable={false}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#ffffff15" gap={18} size={1.5} />
          <Controls showInteractive={false} className="!bg-white/[0.04] !border-white/[0.08]" />
        </ReactFlow>
      </div>

      {modalNode && (
        <PipelineErrorModal
          open
          onClose={() => setModalNode(null)}
          nodeName={modalNode.nodeName}
          graph={modalNode.graph}
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
