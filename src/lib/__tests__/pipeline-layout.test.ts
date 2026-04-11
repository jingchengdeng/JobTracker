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
