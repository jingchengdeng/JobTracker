"use client";

type ShowToast = (message: string, href?: string) => void;

let toastHandler: ShowToast | null = null;
let lastShown = 0;
const DEDUP_WINDOW_MS = 5000;

export function registerEmbeddingMismatchToast(handler: ShowToast) {
  toastHandler = handler;
}

/** Wraps fetch; on 409 with embedding_mismatch, shows a toast. */
export async function fetchWithEmbeddingCheck(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const res = await fetch(input, init);
  if (res.status === 409) {
    try {
      const clone = res.clone();
      const body = await clone.json();
      const detail = body.detail ?? body;
      if (detail?.error === "embedding_mismatch" && toastHandler) {
        const now = Date.now();
        if (now - lastShown > DEDUP_WINDOW_MS) {
          lastShown = now;
          toastHandler(
            "Embedding model mismatch. Reindex required.",
            "/resumes",
          );
        }
      }
    } catch {
      // body not JSON; ignore
    }
  }
  return res;
}
