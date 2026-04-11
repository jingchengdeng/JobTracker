import { describe, it, expect } from "vitest";
import {
  parseKey,
  isNewer,
  reindex,
  lookupState,
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

  it("aligns resume root under master:resume_branch within tolerance", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const branch = nodes.find((n) => n.id === "master:resume_branch")!;
    const root = nodes.find((n) => n.id === "resume:jd_analysis")!;
    expect(Math.abs(branch.position.x - root.position.x)).toBeLessThan(50);
  });

  it("aligns linkedin root under master:linkedin_branch within tolerance", () => {
    const { nodes } = layoutGraphs(TOPOLOGY);
    const branch = nodes.find((n) => n.id === "master:linkedin_branch")!;
    const root = nodes.find((n) => n.id === "linkedin:load_job")!;
    expect(Math.abs(branch.position.x - root.position.x)).toBeLessThan(50);
  });

  it("emits backend edges plus the two cross-graph connectors", () => {
    const { edges } = layoutGraphs(TOPOLOGY);
    const ids = new Set(edges.map((e) => e.id));
    expect(ids.has("connector:master:resume_branch->resume:jd_analysis")).toBe(true);
    expect(ids.has("connector:master:linkedin_branch->linkedin:load_job")).toBe(true);
    expect(edges.some((e) => e.source === "master:extract_fields" && e.target === "master:resolve_default_resume")).toBe(true);
  });
});
