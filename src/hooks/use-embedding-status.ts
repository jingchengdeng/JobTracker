"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { EmbeddingStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export function useEmbeddingStatus() {
  const [status, setStatus] = useState<EmbeddingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/ai/embedding/status");
      if (!res.ok) throw new Error(`status ${res.status}`);
      const data: EmbeddingStatus = await res.json();
      setStatus(data);
      setError(null);
      return data;
    } catch (err) {
      setError(String(err));
      return null;
    }
  }, []);

  const scheduleNext = useCallback(
    (data: EmbeddingStatus | null) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (data?.active_job?.status === "running") {
        timerRef.current = setTimeout(async () => {
          const next = await fetchStatus();
          scheduleNext(next);
        }, POLL_INTERVAL_MS);
      }
    },
    [fetchStatus],
  );

  useEffect(() => {
    fetchStatus().then(scheduleNext);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [fetchStatus, scheduleNext]);

  return { status, error, refresh: fetchStatus };
}
