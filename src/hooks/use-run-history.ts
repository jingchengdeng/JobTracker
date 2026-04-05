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
  const mountedRef = useRef(true);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai/jobs/${jobId}/runs`);
      if (!res.ok) throw new Error(`status ${res.status}`);
      const data: RunSummary[] = await res.json();
      if (mountedRef.current) {
        setRuns(data);
        setError(null);
        setLoading(false);
      }
      return data;
    } catch (err) {
      if (mountedRef.current) {
        setError(String(err));
        setLoading(false);
      }
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    fetchRuns();
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchRuns]);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!hasActive(runs)) return;
    timerRef.current = setTimeout(() => {
      fetchRuns();
    }, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [runs, fetchRuns]);

  return { runs, loading, error, refresh: fetchRuns };
}
