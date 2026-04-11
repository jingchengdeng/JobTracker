export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type NodeState = {
  status: NodeStatus;
  attempt: number;
  durationMs: number | null;
  error: string | null;
  traceback: string | null;
  startedAt: string | null;
  completedAt: string | null;
  workflowRunId: string;
  version: number;
};

export type NodeStateMap = Map<string, NodeState>;

export type LatestByNode = Map<string, NodeState>;

export type ParsedKey = {
  workflowRunId: string;
  graph: string;
  nodeName: string;
  roundNumber: number;
  version: number;
};

/**
 * Parse `workflow_run_id:graph:node_name:round_number:version`. The trailing
 * two segments must be integers. Everything between the second colon and
 * those trailing integers is the node name.
 */
export function parseKey(key: string): ParsedKey | undefined {
  const parts = key.split(":");
  if (parts.length < 5) return undefined;

  const version = Number(parts[parts.length - 1]);
  const roundNumber = Number(parts[parts.length - 2]);
  if (!Number.isInteger(version) || !Number.isInteger(roundNumber)) return undefined;

  const workflowRunId = parts[0];
  const graph = parts[1];
  const nodeName = parts.slice(2, parts.length - 2).join(":");
  if (!workflowRunId || !graph || !nodeName) return undefined;

  return { workflowRunId, graph, nodeName, roundNumber, version };
}

/** Sort key: (version DESC, attempt DESC, startedAt DESC). */
export function isNewer(a: NodeState, b: NodeState): boolean {
  if (a.version !== b.version) return a.version > b.version;
  if (a.attempt !== b.attempt) return a.attempt > b.attempt;
  return (a.startedAt ?? "") > (b.startedAt ?? "");
}

/** Collapse the long-key state map to the latest state per (graph, nodeName). */
export function reindex(map: NodeStateMap): LatestByNode {
  const out: LatestByNode = new Map();
  for (const [k, v] of map.entries()) {
    const parsed = parseKey(k);
    if (!parsed) continue;
    const shortKey = `${parsed.graph}:${parsed.nodeName}`;
    const prev = out.get(shortKey);
    if (!prev || isNewer(v, prev)) out.set(shortKey, v);
  }
  return out;
}

export function lookupState(
  index: LatestByNode,
  graph: string,
  nodeName: string,
): NodeState | undefined {
  return index.get(`${graph}:${nodeName}`);
}

import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "@xyflow/react";

export type TopologyNode = {
  id: string;
  graph: string;
  label: string;
};

export type TopologyEdge = {
  source: string;
  target: string;
  conditional: boolean;
};

export type TopologyGraph = {
  id: string;
  nodes: TopologyNode[];
  edges: TopologyEdge[];
};

export type TopologyConnector = {
  from: string;
  to: string;
};

export type Topology = {
  graphs: TopologyGraph[];
  connectors: TopologyConnector[];
  error?: string;
};

const NODE_WIDTH = 180;
const NODE_HEIGHT = 52;
const GRAPH_GAP_Y = 40;
const COLUMN_GAP_X = 120;

type LaidOutGraph = {
  id: string;
  nodes: Node[];
  edges: Edge[];
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
};

function layoutSingle(graph: TopologyGraph): LaidOutGraph {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 24, ranksep: 32, marginx: 16, marginy: 16 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of graph.nodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const e of graph.edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  const nodes: Node[] = graph.nodes.map((n) => {
    const pos = g.node(n.id);
    // Dagre reports center positions; ReactFlow expects top-left.
    const x = pos.x - NODE_WIDTH / 2;
    const y = pos.y - NODE_HEIGHT / 2;
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x + NODE_WIDTH > maxX) maxX = x + NODE_WIDTH;
    if (y + NODE_HEIGHT > maxY) maxY = y + NODE_HEIGHT;
    return {
      id: `${graph.id}:${n.id}`,
      type: "pipelineNode",
      position: { x, y },
      data: { graph: graph.id, nodeName: n.id, label: n.label },
    };
  });

  const edges: Edge[] = graph.edges.map((e) => ({
    id: `${graph.id}:${e.source}->${e.target}`,
    source: `${graph.id}:${e.source}`,
    target: `${graph.id}:${e.target}`,
    type: "smoothstep",
    animated: false,
    style: { strokeDasharray: e.conditional ? "4 4" : undefined },
  }));

  return { id: graph.id, nodes, edges, minX, minY, maxX, maxY };
}

function shift(laid: LaidOutGraph, dx: number, dy: number): LaidOutGraph {
  return {
    ...laid,
    nodes: laid.nodes.map((n) => ({ ...n, position: { x: n.position.x + dx, y: n.position.y + dy } })),
    minX: laid.minX + dx,
    maxX: laid.maxX + dx,
    minY: laid.minY + dy,
    maxY: laid.maxY + dy,
  };
}

function findNode(laid: LaidOutGraph, suffix: string): Node | undefined {
  return laid.nodes.find((n) => n.id === `${laid.id}:${suffix}`);
}

function stitch(graphs: LaidOutGraph[]): { nodes: Node[]; edges: Edge[] } {
  const master = graphs.find((g) => g.id === "master");
  const resume = graphs.find((g) => g.id === "resume");
  const linkedin = graphs.find((g) => g.id === "linkedin");
  if (!master) {
    return {
      nodes: graphs.flatMap((g) => g.nodes),
      edges: graphs.flatMap((g) => g.edges),
    };
  }

  const subY = master.maxY + GRAPH_GAP_Y;

  let resumeShifted: LaidOutGraph | undefined = resume;
  if (resume) {
    const resumeBranch = findNode(master, "resume_branch");
    const resumeRoot = findNode(resume, "jd_analysis");
    const dx = resumeBranch && resumeRoot ? resumeBranch.position.x - resumeRoot.position.x : 0;
    resumeShifted = shift(resume, dx, subY - resume.minY);
  }

  let linkedinShifted: LaidOutGraph | undefined = linkedin;
  if (linkedin) {
    const linkedinBranch = findNode(master, "linkedin_branch");
    const linkedinRoot = findNode(linkedin, "load_job");
    const dx = linkedinBranch && linkedinRoot ? linkedinBranch.position.x - linkedinRoot.position.x : 0;
    linkedinShifted = shift(linkedin, dx, subY - linkedin.minY);
  }

  if (resumeShifted && linkedinShifted && linkedinShifted.minX < resumeShifted.maxX) {
    const dx = resumeShifted.maxX + COLUMN_GAP_X - linkedinShifted.minX;
    linkedinShifted = shift(linkedinShifted, dx, 0);
  }

  const ordered: LaidOutGraph[] = [master];
  if (resumeShifted) ordered.push(resumeShifted);
  if (linkedinShifted) ordered.push(linkedinShifted);

  return {
    nodes: ordered.flatMap((g) => g.nodes),
    edges: ordered.flatMap((g) => g.edges),
  };
}

export function layoutGraphs(topology: Topology): { nodes: Node[]; edges: Edge[] } {
  const laid = topology.graphs.map((g) => layoutSingle(g));
  const stitched = stitch(laid);
  const connectorEdges: Edge[] = topology.connectors.map((c) => ({
    id: `connector:${c.from}->${c.to}`,
    source: c.from,
    target: c.to,
    type: "smoothstep",
    animated: false,
    style: { stroke: "rgba(148,163,184,0.45)" },
  }));
  return { nodes: stitched.nodes, edges: [...stitched.edges, ...connectorEdges] };
}
