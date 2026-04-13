import { describe, it, expect } from "vitest";
import {
  parseKey,
  isNewer,
  reindex,
  lookupState,
  deriveDisplayStatus,
  type NodeState,
  type NodeStateMap,
} from "../pipeline-layout";

function state(partial: Partial<NodeState> = {}): NodeState {
  return {
    status: "completed",
    attempt: 1,
    durationMs: 100,
    error: null,
    traceback: null,
    startedAt: "2026-04-10T00:00:00Z",
    completedAt: null,
    workflowRunId: "wf-1",
    version: 1,
    ...partial,
  };
}

describe("parseKey", () => {
  it("splits a valid composite key", () => {
    const key = "aaaa-bbbb-cccc:master:extract_fields:0:1";
    expect(parseKey(key)).toEqual({
      workflowRunId: "aaaa-bbbb-cccc",
      graph: "master",
      nodeName: "extract_fields",
      roundNumber: 0,
      version: 1,
    });
  });

  it("rejects keys with a non-integer tail", () => {
    expect(parseKey("wf:master:extract_fields:0:notanum")).toBeUndefined();
    expect(parseKey("wf:master:extract_fields")).toBeUndefined();
  });

  it("handles node names that contain colons", () => {
    const key = "wf:linkedin:weird:name:2:3";
    expect(parseKey(key)).toEqual({
      workflowRunId: "wf",
      graph: "linkedin",
      nodeName: "weird:name",
      roundNumber: 2,
      version: 3,
    });
  });
});

describe("isNewer", () => {
  it("higher version wins", () => {
    expect(isNewer(state({ version: 2 }), state({ version: 1 }))).toBe(true);
  });
  it("same version, higher attempt wins", () => {
    expect(isNewer(state({ version: 1, attempt: 3 }), state({ version: 1, attempt: 2 }))).toBe(true);
  });
  it("same version/attempt, later startedAt wins", () => {
    const a = state({ startedAt: "2026-04-10T00:00:02Z" });
    const b = state({ startedAt: "2026-04-10T00:00:01Z" });
    expect(isNewer(a, b)).toBe(true);
  });
  it("tie on all three returns false", () => {
    expect(isNewer(state(), state())).toBe(false);
  });
});

describe("reindex + lookupState", () => {
  it("collapses duplicates to the latest per (graph, nodeName)", () => {
    const map: NodeStateMap = new Map();
    map.set("wf-1:master:extract_fields:0:1", state({ version: 1 }));
    map.set("wf-1:master:extract_fields:0:2", state({ version: 2 }));
    map.set("wf-1:master:validate_fields:0:1", state());

    const index = reindex(map);
    expect(index.size).toBe(2);

    const latest = lookupState(index, "master", "extract_fields");
    expect(latest?.version).toBe(2);
    expect(lookupState(index, "master", "validate_fields")).toBeDefined();
    expect(lookupState(index, "master", "nonexistent")).toBeUndefined();
  });

  it("ignores entries with malformed keys", () => {
    const map: NodeStateMap = new Map();
    map.set("garbage", state());
    map.set("wf-1:master:extract_fields:0:1", state());
    expect(reindex(map).size).toBe(1);
  });
});

import { layoutGraphs, type Topology } from "../pipeline-layout";

const TOPOLOGY: Topology = {
  graphs: [
    {
      id: "master",
      nodes: [
        { id: "extract_fields", graph: "master", label: "extract_fields" },
        { id: "resolve_default_resume", graph: "master", label: "resolve_default_resume" },
        { id: "resume_branch", graph: "master", label: "resume_branch" },
        { id: "linkedin_branch", graph: "master", label: "linkedin_branch" },
      ],
      edges: [
        { source: "extract_fields", target: "resolve_default_resume", conditional: false },
        { source: "resolve_default_resume", target: "resume_branch", conditional: true },
        { source: "resolve_default_resume", target: "linkedin_branch", conditional: true },
      ],
    },
    {
      id: "resume",
      nodes: [
        { id: "jd_analysis", graph: "resume", label: "jd_analysis" },
        { id: "rag_retrieval", graph: "resume", label: "rag_retrieval" },
      ],
      edges: [
        { source: "jd_analysis", target: "rag_retrieval", conditional: false },
      ],
    },
    {
      id: "linkedin",
      nodes: [
        { id: "load_job", graph: "linkedin", label: "load_job" },
        { id: "precondition_check", graph: "linkedin", label: "precondition_check" },
      ],
      edges: [
        { source: "load_job", target: "precondition_check", conditional: false },
      ],
    },
  ],
  connectors: [
    { from: "master:resume_branch", to: "resume:jd_analysis" },
    { from: "master:linkedin_branch", to: "linkedin:load_job" },
  ],
};

describe("layoutGraphs", () => {
  it("produces finite x/y for every node", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    expect(nodes.length).toBe(8);
    for (const n of nodes) {
      expect(Number.isFinite(n.position.x)).toBe(true);
      expect(Number.isFinite(n.position.y)).toBe(true);
    }
  });

  it("prefixes ids with the graph id", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const ids = new Set(nodes.map((n) => n.id));
    expect(ids.has("master:extract_fields")).toBe(true);
    expect(ids.has("resume:jd_analysis")).toBe(true);
    expect(ids.has("linkedin:load_job")).toBe(true);
  });

  it("aligns resume root exactly under master:resume_branch", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const branch = nodes.find((n) => n.id === "master:resume_branch")!;
    const root = nodes.find((n) => n.id === "resume:jd_analysis")!;
    expect(Math.abs(branch.position.x - root.position.x)).toBeLessThanOrEqual(1);
  });

  it("aligns linkedin root exactly under master:linkedin_branch", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const branch = nodes.find((n) => n.id === "master:linkedin_branch")!;
    const root = nodes.find((n) => n.id === "linkedin:load_job")!;
    expect(Math.abs(branch.position.x - root.position.x)).toBeLessThanOrEqual(1);
  });

  it("keeps resume and linkedin subgraphs horizontally disjoint", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const resumeNodes = nodes.filter((n) => n.id.startsWith("resume:"));
    const linkedinNodes = nodes.filter((n) => n.id.startsWith("linkedin:"));
    const resumeMaxX = Math.max(...resumeNodes.map((n) => n.position.x));
    const linkedinMinX = Math.min(...linkedinNodes.map((n) => n.position.x));
    expect(linkedinMinX).toBeGreaterThan(resumeMaxX);
  });

  it("places subgraphs below the master graph", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const masterMaxY = Math.max(
      ...nodes.filter((n) => n.id.startsWith("master:")).map((n) => n.position.y),
    );
    const subMinY = Math.min(
      ...nodes
        .filter((n) => n.id.startsWith("resume:") || n.id.startsWith("linkedin:"))
        .map((n) => n.position.y),
    );
    expect(subMinY).toBeGreaterThan(masterMaxY);
  });

  it("emits backend edges plus the two cross-graph connectors", () => {
    const { edges } = layoutGraphs(TOPOLOGY);
    const ids = new Set(edges.map((e) => e.id));
    expect(ids.has("connector:master:resume_branch->resume:jd_analysis")).toBe(true);
    expect(ids.has("connector:master:linkedin_branch->linkedin:load_job")).toBe(true);
    expect(edges.some((e) => e.source === "master:extract_fields" && e.target === "master:resolve_default_resume")).toBe(true);
  });
});

// --- deriveDisplayStatus ---------------------------------------------------

const MASTER_WITH_FAIL: Topology = {
  graphs: [
    {
      id: "master",
      nodes: [
        { id: "extract_fields", graph: "master", label: "extract_fields" },
        { id: "validate_fields", graph: "master", label: "validate_fields" },
        { id: "insert_job", graph: "master", label: "insert_job" },
        { id: "fail_node", graph: "master", label: "fail_node" },
      ],
      edges: [
        { source: "extract_fields", target: "validate_fields", conditional: false },
        { source: "validate_fields", target: "insert_job", conditional: true },
        { source: "validate_fields", target: "extract_fields", conditional: true },
        { source: "validate_fields", target: "fail_node", conditional: true },
      ],
    },
  ],
  connectors: [],
};

const LINKEDIN_SUBSET: Topology = {
  graphs: [
    {
      id: "linkedin",
      nodes: [
        { id: "load_brave_key", graph: "linkedin", label: "load_brave_key" },
        { id: "brave_domain_search", graph: "linkedin", label: "brave_domain_search" },
        { id: "enrich_company_apollo", graph: "linkedin", label: "enrich_company_apollo" },
        { id: "build_queries", graph: "linkedin", label: "build_queries" },
        { id: "run_brave_searches", graph: "linkedin", label: "run_brave_searches" },
        { id: "run_browser_searches", graph: "linkedin", label: "run_browser_searches" },
        { id: "merge_dedup", graph: "linkedin", label: "merge_dedup" },
      ],
      edges: [
        { source: "load_brave_key", target: "brave_domain_search", conditional: true },
        { source: "load_brave_key", target: "enrich_company_apollo", conditional: true },
        { source: "brave_domain_search", target: "enrich_company_apollo", conditional: false },
        { source: "enrich_company_apollo", target: "build_queries", conditional: false },
        { source: "build_queries", target: "run_brave_searches", conditional: true },
        { source: "build_queries", target: "run_browser_searches", conditional: true },
        { source: "run_brave_searches", target: "merge_dedup", conditional: true },
        { source: "run_browser_searches", target: "merge_dedup", conditional: true },
      ],
    },
  ],
  connectors: [],
};

const RESUME_CHAIN: Topology = {
  graphs: [
    {
      id: "resume",
      nodes: [
        { id: "jd_analysis", graph: "resume", label: "jd_analysis" },
        { id: "rag_retrieval", graph: "resume", label: "rag_retrieval" },
        { id: "gap_analysis", graph: "resume", label: "gap_analysis" },
      ],
      edges: [
        { source: "jd_analysis", target: "rag_retrieval", conditional: false },
        { source: "rag_retrieval", target: "gap_analysis", conditional: false },
      ],
    },
  ],
  connectors: [],
};

function indexFrom(entries: Array<{ graph: string; node: string; status: NodeState["status"]; attempt?: number }>) {
  const map: NodeStateMap = new Map();
  let seq = 1;
  for (const e of entries) {
    map.set(`wf-1:${e.graph}:${e.node}:0:1`, state({ status: e.status, attempt: e.attempt ?? 1, startedAt: `2026-04-10T00:00:0${seq++}Z` }));
  }
  return reindex(map);
}

describe("deriveDisplayStatus", () => {
  it("returns the real status when a node has state", () => {
    const index = indexFrom([{ graph: "master", node: "insert_job", status: "running" }]);
    expect(deriveDisplayStatus(MASTER_WITH_FAIL, index, "master", "insert_job")).toBe("running");
  });

  it("marks fail_node as skipped once insert_job has a state (Rule A)", () => {
    const index = indexFrom([
      { graph: "master", node: "extract_fields", status: "completed" },
      { graph: "master", node: "validate_fields", status: "completed" },
      { graph: "master", node: "insert_job", status: "running" },
    ]);
    expect(deriveDisplayStatus(MASTER_WITH_FAIL, index, "master", "fail_node")).toBe("skipped");
  });

  it("leaves fail_node pending before validate_fields completes", () => {
    const index = indexFrom([
      { graph: "master", node: "extract_fields", status: "completed" },
      { graph: "master", node: "validate_fields", status: "running" },
    ]);
    expect(deriveDisplayStatus(MASTER_WITH_FAIL, index, "master", "fail_node")).toBe("pending");
  });

  it("marks brave_domain_search skipped when load_brave_key routes to enrich_company_apollo", () => {
    const index = indexFrom([
      { graph: "linkedin", node: "load_brave_key", status: "completed" },
      { graph: "linkedin", node: "enrich_company_apollo", status: "completed" },
    ]);
    expect(deriveDisplayStatus(LINKEDIN_SUBSET, index, "linkedin", "brave_domain_search")).toBe("skipped");
  });

  it("marks run_browser_searches skipped when run_brave_searches was chosen", () => {
    const index = indexFrom([
      { graph: "linkedin", node: "build_queries", status: "completed" },
      { graph: "linkedin", node: "run_brave_searches", status: "completed" },
      { graph: "linkedin", node: "merge_dedup", status: "running" },
    ]);
    expect(deriveDisplayStatus(LINKEDIN_SUBSET, index, "linkedin", "run_browser_searches")).toBe("skipped");
  });

  it("marks jd_analysis/rag_retrieval skipped when the workflow moved past them via the conditional entry (Rule B)", () => {
    const index = indexFrom([
      { graph: "resume", node: "gap_analysis", status: "completed" },
    ]);
    expect(deriveDisplayStatus(RESUME_CHAIN, index, "resume", "jd_analysis")).toBe("skipped");
    expect(deriveDisplayStatus(RESUME_CHAIN, index, "resume", "rag_retrieval")).toBe("skipped");
  });

  it("leaves a downstream node pending when nothing after it has a state", () => {
    const index = indexFrom([{ graph: "resume", node: "jd_analysis", status: "running" }]);
    expect(deriveDisplayStatus(RESUME_CHAIN, index, "resume", "rag_retrieval")).toBe("pending");
    expect(deriveDisplayStatus(RESUME_CHAIN, index, "resume", "gap_analysis")).toBe("pending");
  });

  it("returns pending for unknown graphs instead of crashing", () => {
    const index = indexFrom([]);
    expect(deriveDisplayStatus(RESUME_CHAIN, index, "does_not_exist", "anything")).toBe("pending");
  });
});
