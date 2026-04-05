"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { RunSummary } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

function hasActive(runs: RunSummary[]) {
  return runs.some((r) => r.status === "running" || r.status === "pending");
}

export function useRunHistory(jobId: number) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai/jobs/${jobId}/runs`);
      if (!res.ok) throw new Error(`status ${res.status}`);
      const data: RunSummary[] = await res.json();
      setRuns(data);
      setError(null);
      setLoading(false);
      return data;
    } catch (err) {
      setError(String(err));
      setLoading(false);
      return null;
    }
  }, [jobId]);

  const scheduleNext = useCallback(
    (data: RunSummary[] | null) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (data && hasActive(data)) {
        timerRef.current = setTimeout(async () => {
          const next = await fetchRuns();
          scheduleNext(next);
        }, POLL_INTERVAL_MS);
      }
    },
    [fetchRuns],
  );

  useEffect(() => {
    setLoading(true);
    fetchRuns().then(scheduleNext);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchRuns, scheduleNext]);

  return { runs, loading, error, refresh: fetchRuns };
}
