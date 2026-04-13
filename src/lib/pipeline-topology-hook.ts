"use client";

import { useEffect, useState, useCallback } from "react";
import type { Topology } from "./pipeline-layout";

let cachedPromise: Promise<Topology> | null = null;
let cachedData: Topology | null = null;

async function fetchTopology(): Promise<Topology> {
  const resp = await fetch("/api/ai/pipeline/topology");
  if (!resp.ok) throw new Error(`topology fetch failed: ${resp.status}`);
  return (await resp.json()) as Topology;
}

function getOrStartFetch(): Promise<Topology> {
  if (cachedData) return Promise.resolve(cachedData);
  if (!cachedPromise) {
    cachedPromise = fetchTopology()
      .then((data) => {
        cachedData = data;
        return data;
      })
      .catch((err) => {
        // Clear the cached promise so the next caller / retry() can fire a
        // fresh network call. Without this, a rejected promise would be
        // cached forever and retry would be a no-op.
        cachedPromise = null;
        throw err;
      });
  }
  return cachedPromise;
}

export function __resetTopologyCache() {
  cachedPromise = null;
  cachedData = null;
}

export function useTopology(): {
  data: Topology | null;
  error: Error | null;
  retry: () => void;
} {
  const [data, setData] = useState<Topology | null>(cachedData);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getOrStartFetch()
      .then((t) => {
        if (!cancelled) setData(t);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const retry = useCallback(() => {
    cachedData = null;
    cachedPromise = null;
    setData(null);
    setError(null);
    setTick((t) => t + 1);
  }, []);

  return { data, error, retry };
}
