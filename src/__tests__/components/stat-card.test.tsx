import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "@/components/stat-card";

describe("StatCard", () => {
  it("renders label and numeric value", () => {
    render(<StatCard label="Total Applied" value={42} />);
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("Total Applied")).toBeInTheDocument();
  });

  it("renders string value", () => {
    render(<StatCard label="Response Rate" value="85%" />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("applies color style when provided", () => {
    render(<StatCard label="Interviews" value={7} color="#22c55e" />);
    const valueEl = screen.getByText("7");
    expect(valueEl).toHaveStyle({ color: "#22c55e" });
  });

  it("has no inline color when not provided", () => {
    render(<StatCard label="Total" value={10} />);
    const valueEl = screen.getByText("10");
    expect(valueEl.style.color).toBe("");
  });
});
