"use client";

import type { EmbeddingStatus } from "@/lib/types";

interface Props {
  status: EmbeddingStatus;
  onReindex: (resumeIds?: number[]) => void;
}

export function EmbeddingStatusBanner({ status, onReindex }: Props) {
  const { active_signature, configured_signature, resumes, active_job } = status;

  if (active_job?.status === "running") {
    const done = active_job.succeeded.length + active_job.failed.length;
    return (
      <div className="rounded-md border border-blue-300 bg-blue-50 p-3 text-blue-900">
        <p className="font-medium">Reindexing {done}/{active_job.total}…</p>
      </div>
    );
  }

  const failed = resumes.filter((r) => r.last_index_status === "failed");
  if (failed.length > 0) {
    return (
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-red-900 flex items-center justify-between">
        <p>{failed.length} of {resumes.length} resumes failed to reindex.</p>
        <button
          type="button"
          aria-label="Retry Failed"
          onClick={() => onReindex(failed.map((r) => r.id))}
          className="rounded bg-red-600 px-3 py-1 text-sm text-white"
        >
          Retry
        </button>
      </div>
    );
  }

  if (active_signature === null) {
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 flex items-center justify-between">
        <p>Initial indexing required.</p>
        <button
          type="button"
          onClick={() => onReindex(undefined)}
          className="rounded bg-amber-600 px-3 py-1 text-sm text-white"
        >
          Index All
        </button>
      </div>
    );
  }

  if (active_signature !== configured_signature) {
    const stale = resumes.filter(
      (r) => r.last_index_signature !== configured_signature
    ).length;
    return (
      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 flex items-center justify-between">
        <p>Embedding model changed. {stale} resumes need reindexing.</p>
        <button
          type="button"
          onClick={() => onReindex(undefined)}
          className="rounded bg-amber-600 px-3 py-1 text-sm text-white"
        >
          Reindex All
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-green-300 bg-green-50 p-3 text-green-900">
      <p>All resumes indexed ({active_signature}).</p>
    </div>
  );
}
