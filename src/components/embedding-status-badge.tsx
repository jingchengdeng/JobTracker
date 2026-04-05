"use client";

import type { EmbeddingResumeStatus } from "@/lib/types";

interface Props {
  resumeStatus: EmbeddingResumeStatus;
  activeSignature: string | null;
  configuredSignature: string;
  isIndexing: boolean;
}

export function EmbeddingStatusBadge({
  resumeStatus,
  activeSignature,
  configuredSignature,
  isIndexing,
}: Props) {
  if (isIndexing) {
    return (
      <span className="inline-flex items-center rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-800">
        Indexing…
      </span>
    );
  }
  if (resumeStatus.last_index_status === "failed") {
    return (
      <span
        title={resumeStatus.last_index_error ?? ""}
        className="inline-flex items-center rounded bg-red-100 px-2 py-0.5 text-xs text-red-800"
      >
        Failed
      </span>
    );
  }
  if (
    resumeStatus.last_index_status === "ok" &&
    resumeStatus.last_index_signature === activeSignature &&
    resumeStatus.last_index_signature === configuredSignature
  ) {
    return (
      <span className="inline-flex items-center rounded bg-green-100 px-2 py-0.5 text-xs text-green-800">
        Indexed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
      Stale
    </span>
  );
}
