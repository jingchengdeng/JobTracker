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
