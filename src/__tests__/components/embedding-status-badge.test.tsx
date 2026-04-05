import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmbeddingStatusBadge } from "@/components/embedding-status-badge";

describe("EmbeddingStatusBadge", () => {
  it("shows green when indexed at active signature", () => {
    render(
      <EmbeddingStatusBadge
        resumeStatus={{ id: 1, name: "a", last_index_signature: "sig", last_index_status: "ok", last_index_error: null }}
        activeSignature="sig"
        configuredSignature="sig"
        isIndexing={false}
      />
    );
    expect(screen.getByText("Indexed")).toBeInTheDocument();
  });

  it("shows stale when signature differs from configured", () => {
    render(
      <EmbeddingStatusBadge
        resumeStatus={{ id: 1, name: "a", last_index_signature: "old", last_index_status: "ok", last_index_error: null }}
        activeSignature="old"
        configuredSignature="new"
        isIndexing={false}
      />
    );
    expect(screen.getByText("Stale")).toBeInTheDocument();
  });

  it("shows failed with tooltip error", () => {
    render(
      <EmbeddingStatusBadge
        resumeStatus={{ id: 1, name: "a", last_index_signature: null, last_index_status: "failed", last_index_error: "rate limit" }}
        activeSignature="sig"
        configuredSignature="sig"
        isIndexing={false}
      />
    );
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByTitle("rate limit")).toBeInTheDocument();
  });

  it("shows indexing spinner when currently in-progress", () => {
    render(
      <EmbeddingStatusBadge
        resumeStatus={{ id: 1, name: "a", last_index_signature: null, last_index_status: "pending", last_index_error: null }}
        activeSignature="sig"
        configuredSignature="sig"
        isIndexing={true}
      />
    );
    expect(screen.getByText("Indexing…")).toBeInTheDocument();
  });
});
