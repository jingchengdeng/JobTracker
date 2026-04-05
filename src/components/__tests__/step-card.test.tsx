import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StepCard } from "@/components/step-card";
import type { StepData } from "@/lib/group-by-round";

const step = (overrides: Partial<StepData> = {}): StepData => ({
  id: 1, step_type: "rewrite", status: "completed",
  result: '{"rewritten_resume": "The full resume text."}',
  version: 1, round_number: 0,
  ...overrides,
});

describe("StepCard", () => {
  it("renders header with step label and completed check", () => {
    render(<StepCard step={step()} expanded={true} onToggle={vi.fn()} />);
    expect(screen.getByText(/rewrite/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/completed/i)).toBeInTheDocument();
  });

  it("shows a spinner when status is running", () => {
    render(<StepCard step={step({ status: "running" })} expanded={true} onToggle={vi.fn()} />);
    expect(screen.getByLabelText(/running/i)).toBeInTheDocument();
  });

  it("hides body when collapsed", () => {
    render(<StepCard step={step()} expanded={false} onToggle={vi.fn()} />);
    expect(screen.queryByText(/The full resume text/)).not.toBeInTheDocument();
  });

  it("shows body when expanded", () => {
    render(<StepCard step={step()} expanded={true} onToggle={vi.fn()} />);
    expect(screen.getByText(/The full resume text/)).toBeInTheDocument();
  });

  it("calls onToggle when header clicked", () => {
    const onToggle = vi.fn();
    render(<StepCard step={step()} expanded={false} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("button", { name: /rewrite/i }));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("shows error text in header when failed, even if collapsed", () => {
    render(
      <StepCard
        step={step({ status: "failed", result: "LLM timeout" })}
        expanded={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText(/LLM timeout/)).toBeInTheDocument();
  });
});
