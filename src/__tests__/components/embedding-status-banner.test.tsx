import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmbeddingStatusBanner } from "@/components/embedding-status-banner";
import type { EmbeddingStatus } from "@/lib/types";

function makeStatus(overrides: Partial<EmbeddingStatus> = {}): EmbeddingStatus {
  return {
    active_signature: "openai__text_embedding_3_small",
    configured_signature: "openai__text_embedding_3_small",
    resumes: [
      { id: 1, name: "a.pdf", last_index_signature: "openai__text_embedding_3_small", last_index_status: "ok", last_index_error: null },
    ],
    active_job: null,
    ...overrides,
  };
}

describe("EmbeddingStatusBanner", () => {
  it("shows green when all resumes indexed against active signature", () => {
    render(<EmbeddingStatusBanner status={makeStatus()} onReindex={() => {}} />);
    expect(screen.getByText(/all resumes indexed/i)).toBeInTheDocument();
  });

  it("shows amber when configured != active", () => {
    render(
      <EmbeddingStatusBanner
        status={makeStatus({
          configured_signature: "openai__new_model",
          active_signature: "openai__old_model",
        })}
        onReindex={() => {}}
      />
    );
    expect(screen.getByText(/embedding model changed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reindex all/i })).toBeInTheDocument();
  });

  it("shows running progress during active job", () => {
    render(
      <EmbeddingStatusBanner
        status={makeStatus({
          active_job: {
            job_id: "x", status: "running", target_signature: "openai__new",
            started_at: "", completed_at: null, total: 10,
            succeeded: [1, 2, 3], failed: [], current_resume_id: 4,
          },
        })}
        onReindex={() => {}}
      />
    );
    expect(screen.getByText(/reindexing 3\/10/i)).toBeInTheDocument();
  });

  it("shows red when last job had failures", () => {
    render(
      <EmbeddingStatusBanner
        status={makeStatus({
          resumes: [
            { id: 1, name: "a.pdf", last_index_signature: "sig", last_index_status: "ok", last_index_error: null },
            { id: 2, name: "b.pdf", last_index_signature: null, last_index_status: "failed", last_index_error: "rate limit" },
          ],
        })}
        onReindex={() => {}}
      />
    );
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry failed/i })).toBeInTheDocument();
  });

  it("shows initial indexing required when no active signature", () => {
    render(
      <EmbeddingStatusBanner
        status={makeStatus({ active_signature: null })}
        onReindex={() => {}}
      />
    );
    expect(screen.getByText(/initial indexing required/i)).toBeInTheDocument();
  });

  it("calls onReindex with no args for reindex all", () => {
    const onReindex = vi.fn();
    render(
      <EmbeddingStatusBanner
        status={makeStatus({
          configured_signature: "openai__new",
          active_signature: "openai__old",
        })}
        onReindex={onReindex}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /reindex all/i }));
    expect(onReindex).toHaveBeenCalledWith(undefined);
  });

  it("calls onReindex with failed resume_ids for retry failed", () => {
    const onReindex = vi.fn();
    render(
      <EmbeddingStatusBanner
        status={makeStatus({
          resumes: [
            { id: 1, name: "a.pdf", last_index_signature: "sig", last_index_status: "ok", last_index_error: null },
            { id: 2, name: "b.pdf", last_index_signature: null, last_index_status: "failed", last_index_error: "rate limit" },
          ],
        })}
        onReindex={onReindex}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /retry failed/i }));
    expect(onReindex).toHaveBeenCalledWith([2]);
  });
});
