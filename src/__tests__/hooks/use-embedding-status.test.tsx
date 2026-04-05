import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEmbeddingStatus } from "@/hooks/use-embedding-status";

describe("useEmbeddingStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("fetches status on mount", async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        active_signature: "openai__m",
        configured_signature: "openai__m",
        resumes: [],
        active_job: null,
      }),
    });

    const { result } = renderHook(() => useEmbeddingStatus());
    await act(async () => {
      await vi.runAllTimersAsync();
    });
    expect(result.current.status?.active_signature).toBe("openai__m");
  });

  it("polls every 2s when a job is active", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        active_signature: null,
        configured_signature: "openai__m",
        resumes: [],
        active_job: {
          job_id: "j1",
          status: "running",
          target_signature: "openai__m",
          started_at: "2026-04-05T00:00:00Z",
          completed_at: null,
          total: 3,
          succeeded: [],
          failed: [],
          current_resume_id: null,
        },
      }),
    });

    renderHook(() => useEmbeddingStatus());

    // Flush initial mount fetch (Promise resolves, no timer needed)
    await act(async () => {
      await Promise.resolve();
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Advance 2s to fire the scheduled poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it("stops polling when job completes", async () => {
    let call = 0;
    (global.fetch as any).mockImplementation(async () => {
      call++;
      return {
        ok: true,
        json: async () => ({
          active_signature: "openai__m",
          configured_signature: "openai__m",
          resumes: [],
          active_job: call === 1
            ? { job_id: "j1", status: "running", target_signature: "openai__m",
                started_at: "", completed_at: null, total: 1, succeeded: [], failed: [], current_resume_id: null }
            : null,
        }),
      };
    });

    renderHook(() => useEmbeddingStatus());

    // call 1: initial fetch (active_job = running) → schedules a 2s timer
    await act(async () => {
      await Promise.resolve();
    });
    expect(call).toBe(1);

    // Advance 2s → fires timer → call 2: active_job = null → no new timer
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(call).toBe(2);

    // Advance another 2s → no new call
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(call).toBe(2);
  });
});
