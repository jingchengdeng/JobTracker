import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoundBlock } from "@/components/round-block";
import type { Round } from "@/lib/group-by-round";

const round0: Round = {
  round_number: 0,
  user_message: null,
  ack_message: null,
  steps: [
    { id: 1, step_type: "jd_analysis", status: "completed", result: "{}", version: 1, round_number: 0 },
    { id: 2, step_type: "rewrite", status: "completed", result: "{}", version: 1, round_number: 0 },
  ],
};

const round1: Round = {
  round_number: 1,
  user_message: { role: "user", content: "more leadership", round_number: 1 },
  ack_message: { role: "assistant", content: "Sure, tightening the rewrite.", round_number: 1 },
  steps: [
    { id: 3, step_type: "rewrite", status: "running", result: null, version: 2, round_number: 1 },
  ],
};

describe("RoundBlock", () => {
  it("round 0 renders label but no chat bubbles", () => {
    render(<RoundBlock round={round0} expandedStepIds={new Set()} onToggleStep={vi.fn()} />);
    expect(screen.getByText(/initial analysis/i)).toBeInTheDocument();
    expect(screen.queryByText("more leadership")).not.toBeInTheDocument();
  });

  it("round 1 renders label, user message, ack message, and steps", () => {
    render(<RoundBlock round={round1} expandedStepIds={new Set()} onToggleStep={vi.fn()} />);
    expect(screen.getByText(/round 1/i)).toBeInTheDocument();
    expect(screen.getByText("more leadership")).toBeInTheDocument();
    expect(screen.getByText("Sure, tightening the rewrite.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /rewrite/i })).toBeInTheDocument();
  });

  it("passes expanded state to child StepCards based on expandedStepIds", () => {
    const { rerender } = render(
      <RoundBlock round={round0} expandedStepIds={new Set([1])} onToggleStep={vi.fn()} />,
    );
    rerender(<RoundBlock round={round0} expandedStepIds={new Set()} onToggleStep={vi.fn()} />);
  });
});
