import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RunHistorySidebar } from "@/components/run-history-sidebar";
import type { RunSummary } from "@/lib/types";

const base: RunSummary = {
  id: 1, resume_id: 10, resume_name: "AI Engineer Resume", resume_version: "v2",
  status: "completed", error: null, match_score: 82,
  created_at: "2026-04-05T10:00:00Z", completed_at: "2026-04-05T10:01:00Z",
};

describe("RunHistorySidebar", () => {
  it("renders empty state when no runs", () => {
    render(
      <RunHistorySidebar runs={[]} selectedRunId={null} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText(/no analyses yet/i)).toBeInTheDocument();
  });

  it("renders each run with name, version, status, match score", () => {
    render(
      <RunHistorySidebar runs={[base]} selectedRunId={null} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("AI Engineer Resume")).toBeInTheDocument();
    expect(screen.getByText(/v2/)).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
  });

  it("shows dash when match score is null", () => {
    const run: RunSummary = { ...base, match_score: null };
    render(
      <RunHistorySidebar runs={[run]} selectedRunId={null} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("fires onSelect when an entry is clicked", () => {
    const onSelect = vi.fn();
    render(
      <RunHistorySidebar runs={[base]} selectedRunId={null} onSelect={onSelect} onDelete={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /AI Engineer Resume/i }));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("fires onDelete when delete icon is clicked", () => {
    const onDelete = vi.fn();
    render(
      <RunHistorySidebar runs={[base]} selectedRunId={null} onSelect={vi.fn()} onDelete={onDelete} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /delete run/i }));
    expect(onDelete).toHaveBeenCalledWith(1);
  });

  it("disables delete for a running run", () => {
    const run: RunSummary = { ...base, status: "running" };
    render(
      <RunHistorySidebar runs={[run]} selectedRunId={null} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /delete run/i })).toBeDisabled();
  });
});
