import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/status-badge";
import type { JobStatus } from "@/lib/types";

describe("StatusBadge", () => {
  const statuses: { status: JobStatus; label: string }[] = [
    { status: "saved", label: "Saved" },
    { status: "applied", label: "Applied" },
    { status: "phone_screen", label: "Phone Screen" },
    { status: "interview", label: "Interview" },
    { status: "offer", label: "Offer" },
    { status: "accepted", label: "Accepted" },
    { status: "rejected", label: "Rejected" },
    { status: "withdrawn", label: "Withdrawn" },
    { status: "ghosted", label: "Ghosted" },
  ];

  statuses.forEach(({ status, label }) => {
    it(`renders "${label}" for status "${status}"`, () => {
      render(<StatusBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("has distinct styles per status", () => {
    const { rerender } = render(<StatusBadge status="applied" />);
    const appliedEl = screen.getByText("Applied");
    const appliedClass = appliedEl.className;

    rerender(<StatusBadge status="rejected" />);
    const rejectedEl = screen.getByText("Rejected");
    const rejectedClass = rejectedEl.className;

    expect(appliedClass).not.toBe(rejectedClass);
  });
});
