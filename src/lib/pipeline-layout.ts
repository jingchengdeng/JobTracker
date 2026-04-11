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
const GRAPH_GAP_Y = 80;
const COLUMN_GAP_X = 180;
const DEFAULT_NODESEP = 60;
const DEFAULT_RANKSEP = 80;

type LaidOutGraph = {
  id: string;
  nodes: Node[];
  edges: Edge[];
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
};

type LayoutOpts = {
  nodesep?: number;
  ranksep?: number;
};

function layoutSingle(graph: TopologyGraph, opts: LayoutOpts = {}): LaidOutGraph {
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: "TB",
    nodesep: opts.nodesep ?? DEFAULT_NODESEP,
    ranksep: opts.ranksep ?? DEFAULT_RANKSEP,
    marginx: 16,
    marginy: 16,
  });
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

function nodeCenterX(n: Node): number {
  return n.position.x + NODE_WIDTH / 2;
}

type RootGeometry = {
  rootCenterX: number;
  leftExtent: number; // distance from root center to left edge of subgraph
  rightExtent: number; // distance from root center to right edge of subgraph
};

function rootGeometry(sub: LaidOutGraph, rootSuffix: string): RootGeometry | undefined {
  const root = findNode(sub, rootSuffix);
  if (!root) return undefined;
  const rootCenterX = nodeCenterX(root);
  return {
    rootCenterX,
    leftExtent: rootCenterX - sub.minX,
    rightExtent: sub.maxX - rootCenterX,
  };
}

/**
 * Place master at the top, then place each subgraph directly under its own
 * fan-out branch node. Master is laid out with a dynamically computed
 * `nodesep` that guarantees the fan-out siblings are far enough apart for
 * both subgraphs to sit side-by-side underneath without overlapping — no
 * matter which sibling dagre picks as the left one.
 *
 * Without this dynamic nodesep, master's default dagre spacing puts the
 * fan-out siblings ~200px apart while the LinkedIn subgraph alone spans
 * ~500px, forcing the cross-graph connectors into long diagonals that
 * visually tangle both subpipelines together.
 */
function stitch(
  master: LaidOutGraph | undefined,
  resume: LaidOutGraph | undefined,
  linkedin: LaidOutGraph | undefined,
  topology: Topology,
): { nodes: Node[]; edges: Edge[]; all: LaidOutGraph[] } {
  if (!master) {
    const all = [resume, linkedin].filter((g): g is LaidOutGraph => !!g);
    return { nodes: all.flatMap((g) => g.nodes), edges: all.flatMap((g) => g.edges), all };
  }
  if (!resume && !linkedin) {
    return { nodes: master.nodes, edges: master.edges, all: [master] };
  }

  // Compute each subgraph's root geometry relative to its own (un-shifted)
  // layout. We care about how far the root sits from the subgraph's left
  // and right edges so we can pick the minimum master fan-out spacing that
  // keeps them disjoint once each is centered on its branch node.
  const resumeGeom = resume ? rootGeometry(resume, "jd_analysis") : undefined;
  const linkedinGeom = linkedin ? rootGeometry(linkedin, "load_job") : undefined;

  // Required center-to-center distance between master's two branch nodes:
  //   worstCase = max(
  //     resume.rightExtent + linkedin.leftExtent + GAP,   // resume on left
  //     linkedin.rightExtent + resume.leftExtent + GAP,   // linkedin on left
  //   )
  // We take the max because dagre may pick either order; both configurations
  // must fit without overlap.
  let requiredSpan = 0;
  if (resumeGeom && linkedinGeom) {
    const caseA = resumeGeom.rightExtent + linkedinGeom.leftExtent + COLUMN_GAP_X;
    const caseB = linkedinGeom.rightExtent + resumeGeom.leftExtent + COLUMN_GAP_X;
    requiredSpan = Math.max(caseA, caseB);
  }

  // Relayout master with a nodesep that guarantees siblings at the same rank
  // are at least `requiredSpan` center-to-center apart. Dagre's `nodesep` is
  // the edge-to-edge minimum, so center-to-center = nodesep + NODE_WIDTH.
  let masterLaid = master;
  if (requiredSpan > 0) {
    const requiredNodesep = Math.max(DEFAULT_NODESEP, requiredSpan - NODE_WIDTH);
    const masterTopo = topology.graphs.find((g) => g.id === "master");
    if (masterTopo) {
      masterLaid = layoutSingle(masterTopo, { nodesep: requiredNodesep });
    }
  }

  const subY = masterLaid.maxY + GRAPH_GAP_Y;

  // Place each subgraph so its root node sits directly under the matching
  // master branch. Order is derived from whatever master gave us — dagre may
  // have put linkedin_branch on the left or on the right; either works.
  let resumeShifted: LaidOutGraph | undefined;
  let linkedinShifted: LaidOutGraph | undefined;

  if (resume && resumeGeom) {
    const masterResumeBranch = findNode(masterLaid, "resume_branch");
    const targetX = masterResumeBranch ? nodeCenterX(masterResumeBranch) : resumeGeom.rootCenterX;
    const dx = targetX - resumeGeom.rootCenterX;
    resumeShifted = shift(resume, dx, subY - resume.minY);
  }
  if (linkedin && linkedinGeom) {
    const masterLinkedinBranch = findNode(masterLaid, "linkedin_branch");
    const targetX = masterLinkedinBranch ? nodeCenterX(masterLinkedinBranch) : linkedinGeom.rootCenterX;
    const dx = targetX - linkedinGeom.rootCenterX;
    linkedinShifted = shift(linkedin, dx, subY - linkedin.minY);
  }

  const ordered: LaidOutGraph[] = [masterLaid];
  if (resumeShifted) ordered.push(resumeShifted);
  if (linkedinShifted) ordered.push(linkedinShifted);

  return {
    nodes: ordered.flatMap((g) => g.nodes),
    edges: ordered.flatMap((g) => g.edges),
    all: ordered,
  };
}

export function layoutGraphs(topology: Topology): { nodes: Node[]; edges: Edge[] } {
  const laid = topology.graphs.map((g) => layoutSingle(g));
  const master = laid.find((g) => g.id === "master");
  const resume = laid.find((g) => g.id === "resume");
  const linkedin = laid.find((g) => g.id === "linkedin");
  const stitched = stitch(master, resume, linkedin, topology);
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

// ---------------------------------------------------------------------------
// Display-status derivation
// ---------------------------------------------------------------------------
//
// The backend only emits pipeline events for nodes that actually run. Nodes on
// conditional branches that were *not* taken (fail_node when insert_job
// succeeds, run_browser_searches when run_brave_searches was chosen, etc.)
// simply never appear in the state map, so they would default to `pending`
// and look permanently stuck.
//
// `deriveDisplayStatus` computes the rendered status for a node given the
// latest state index and the topology. It returns the real status if present,
// otherwise "skipped" if either of two rules fires:
//
//   Rule B (descendant reached): any forward-reachable node in the same graph
//     has a non-pending state. If the workflow moved past this node without
//     touching it, the only explanation is that the scheduler skipped it.
//
//   Rule A (conditional sibling chosen): the node has a conditional incoming
//     edge from a completed source, and some other conditional target of the
//     same source has a non-pending state. This handles terminal-dead-end
//     nodes like master:fail_node whose only downstream is END.
//
// Otherwise the node stays `pending`.

const STATUS_SETTLED_OR_RUNNING: ReadonlySet<NodeStatus> = new Set([
  "running",
  "completed",
  "failed",
  "skipped",
]);

function forwardAdjacency(graph: TopologyGraph): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const e of graph.edges) {
    if (!out.has(e.source)) out.set(e.source, []);
    out.get(e.source)!.push(e.target);
  }
  return out;
}

function hasDescendantWithState(
  start: string,
  adjacency: Map<string, string[]>,
  index: LatestByNode,
  graphId: string,
): boolean {
  const visited = new Set<string>();
  const stack = [...(adjacency.get(start) ?? [])];
  while (stack.length > 0) {
    const n = stack.pop()!;
    if (visited.has(n)) continue;
    visited.add(n);
    const st = lookupState(index, graphId, n);
    if (st && STATUS_SETTLED_OR_RUNNING.has(st.status)) return true;
    for (const next of adjacency.get(n) ?? []) stack.push(next);
  }
  return false;
}

function hasConditionalSiblingChosen(
  nodeName: string,
  graph: TopologyGraph,
  index: LatestByNode,
): boolean {
  for (const incoming of graph.edges) {
    if (incoming.target !== nodeName || !incoming.conditional) continue;
    const sourceState = lookupState(index, graph.id, incoming.source);
    if (!sourceState || sourceState.status !== "completed") continue;
    for (const other of graph.edges) {
      if (
        other.source === incoming.source &&
        other.target !== nodeName &&
        other.conditional
      ) {
        const otherState = lookupState(index, graph.id, other.target);
        if (otherState && STATUS_SETTLED_OR_RUNNING.has(otherState.status)) {
          return true;
        }
      }
    }
  }
  return false;
}

export function deriveDisplayStatus(
  topology: Topology,
  index: LatestByNode,
  graphId: string,
  nodeName: string,
): NodeStatus {
  const existing = lookupState(index, graphId, nodeName);
  if (existing) return existing.status;

  const graph = topology.graphs.find((g) => g.id === graphId);
  if (!graph) return "pending";

  const adjacency = forwardAdjacency(graph);
  if (hasDescendantWithState(nodeName, adjacency, index, graphId)) return "skipped";
  if (hasConditionalSiblingChosen(nodeName, graph, index)) return "skipped";
  return "pending";
}
