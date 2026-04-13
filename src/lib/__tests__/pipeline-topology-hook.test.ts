import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useTopology, __resetTopologyCache } from "../pipeline-topology-hook";

const MOCK_TOPOLOGY = {
  graphs: [
    { id: "master", nodes: [{ id: "extract_fields", graph: "master", label: "extract_fields" }], edges: [] },
    { id: "resume", nodes: [], edges: [] },
    { id: "linkedin", nodes: [], edges: [] },
  ],
  connectors: [],
};

describe("useTopology", () => {
  beforeEach(() => {
    __resetTopologyCache();
    vi.restoreAllMocks();
  });

  it("hits fetch exactly once across multiple callers", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => MOCK_TOPOLOGY,
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const first = renderHook(() => useTopology());
    const second = renderHook(() => useTopology());

    await waitFor(() => {
      expect(first.result.current.data).not.toBeNull();
      expect(second.result.current.data).not.toBeNull();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/ai/pipeline/topology");
  });

  it("exposes error state when fetch rejects", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("boom"));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTopology());
    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });
    expect(result.current.data).toBeNull();
  });

  it("retry() triggers a fresh fetch after a failure", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({ ok: true, json: async () => MOCK_TOPOLOGY } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTopology());
    await waitFor(() => expect(result.current.error).not.toBeNull());

    await act(async () => {
      result.current.retry();
    });
    await waitFor(() => {
      expect(result.current.data).not.toBeNull();
      expect(result.current.error).toBeNull();
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
