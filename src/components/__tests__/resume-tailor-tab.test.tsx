import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ResumeTailorTab } from "@/components/resume-tailor-tab";
import type { Job } from "@/lib/types";

const job: Job = {
  id: 1, title: "BE", company: "Acme", location: null, url: null, description: "jd",
  salaryMin: null, salaryMax: null, salaryCurrency: null, status: "saved", jobType: null,
  workMode: null, source: null, contactName: null, contactEmail: null, resumeVersion: null,
  notes: null, priority: null, dateApplied: null, interviewDates: null,
  createdAt: "2026-01-01", updatedAt: "2026-01-01",
};

function mockFetchSequence(responses: Array<{ url: RegExp; body: unknown; status?: number }>) {
  const calls: string[] = [];
  global.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push(url);
    const match = responses.find((r) => r.url.test(url));
    if (!match) return { ok: false, status: 404, json: async () => ({}) } as Response;
    return {
      ok: (match.status ?? 200) < 400,
      status: match.status ?? 200,
      json: async () => match.body,
    } as Response;
  }) as typeof global.fetch;
  return calls;
}

describe("ResumeTailorTab — conversation log", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    Element.prototype.scrollIntoView = vi.fn();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders initial round with auto-expanded rewrite card after hydrate", async () => {
    mockFetchSequence([
      { url: /\/api\/resumes$/, body: [{ id: 10, name: "R", version: "v1" }] },
      { url: /\/api\/ai\/jobs\/1\/runs$/, body: [
        { id: 7, resume_id: 10, resume_name: "R", resume_version: "v1",
          status: "completed", error: null, match_score: 80,
          created_at: "2026-04-05T10:00:00", completed_at: "2026-04-05T10:01:00" },
      ] },
      { url: /\/api\/ai\/runs\/7$/, body: {
        id: 7, status: "completed", error: null,
        steps: [
          { id: 100, step_type: "jd_analysis", status: "completed",
            result: '{"title": "T", "company": "C", "key_requirements": [], "technologies": []}',
            version: 1, round_number: 0 },
          { id: 101, step_type: "rewrite", status: "completed",
            result: '{"rewritten_resume": "HELLO", "changes_made": []}',
            version: 1, round_number: 0 },
        ],
      } },
      { url: /\/api\/ai\/runs\/7\/messages$/, body: { messages: [] } },
    ]);

    render(<ResumeTailorTab job={job} />);
    await vi.runAllTimersAsync();

    await waitFor(() => {
      expect(screen.getByText(/initial analysis/i)).toBeInTheDocument();
    });
    expect(screen.getByText("HELLO")).toBeInTheDocument();
  });

  it("composer is always visible and disabled while status is running", async () => {
    mockFetchSequence([
      { url: /\/api\/resumes$/, body: [{ id: 10, name: "R", version: "v1" }] },
      { url: /\/api\/ai\/jobs\/1\/runs$/, body: [
        { id: 7, resume_id: 10, resume_name: "R", resume_version: "v1",
          status: "running", error: null, match_score: null,
          created_at: "2026-04-05T10:00:00", completed_at: null },
      ] },
      { url: /\/api\/ai\/runs\/7$/, body: {
        id: 7, status: "running", error: null, steps: [],
      } },
      { url: /\/api\/ai\/runs\/7\/messages$/, body: { messages: [] } },
    ]);
    render(<ResumeTailorTab job={job} />);
    await vi.runAllTimersAsync();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/ask for another refine|emphasize leadership/i)).toBeInTheDocument();
    });
    const input = screen.getByPlaceholderText(/ask for another refine|emphasize leadership/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "test" } });
    const sendBtn = screen.getAllByRole("button").find((b) => b.querySelector("svg") && b.getAttribute("disabled") !== null);
    expect(sendBtn).toBeTruthy();
  });
});
