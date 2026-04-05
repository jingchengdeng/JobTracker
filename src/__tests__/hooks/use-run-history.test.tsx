import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRunHistory } from "@/hooks/use-run-history";

function mockResponse(runs: unknown) {
  return { ok: true, json: async () => runs };
}

describe("useRunHistory", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("fetches on mount", async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      mockResponse([
        { id: 1, resume_id: 1, resume_name: "r", resume_version: null,
          status: "completed", error: null, match_score: 80,
          created_at: "2026-04-05T10:00:00", completed_at: "2026-04-05T10:01:00" },
      ])
    );
    const { result } = renderHook(() => useRunHistory(42));
    await act(async () => { await vi.runAllTimersAsync(); });
    expect(global.fetch).toHaveBeenCalledWith("/api/ai/jobs/42/runs");
    expect(result.current.runs).toHaveLength(1);
  });

  it("polls every 2s while any run is running", async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockResponse([
        { id: 1, resume_id: 1, resume_name: "r", resume_version: null,
          status: "running", error: null, match_score: null,
          created_at: "2026-04-05T10:00:00", completed_at: null },
      ])
    );
    renderHook(() => useRunHistory(42));
    await act(async () => { await Promise.resolve(); });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("stops polling when all runs are terminal", async () => {
    let call = 0;
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      call++;
      return mockResponse([
        { id: 1, resume_id: 1, resume_name: "r", resume_version: null,
          status: call === 1 ? "running" : "completed",
          error: null, match_score: null,
          created_at: "2026-04-05T10:00:00", completed_at: null },
      ]);
    });
    renderHook(() => useRunHistory(42));
    await act(async () => { await Promise.resolve(); });
    expect(call).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(call).toBe(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(call).toBe(2);
  });

  it("refresh() forces an immediate fetch", async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockResponse([])
    );
    const { result } = renderHook(() => useRunHistory(42));
    await act(async () => { await Promise.resolve(); });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    await act(async () => { await result.current.refresh(); });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });
});
