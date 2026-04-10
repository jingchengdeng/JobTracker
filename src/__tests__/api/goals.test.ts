import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb(), dbReady: Promise.resolve() };
});

const { db } = await import("@/db");

describe("GET /api/goals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns all goals", async () => {
    const goalsList = [
      { id: 1, type: "weekly", target: 5, periodStart: "2026-03-16" },
    ];
    (db as any)._queueResult(goalsList);

    const { GET } = await import("@/app/api/goals/route");
    const res = await GET();
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(goalsList);
  });
});

describe("POST /api/goals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates a new goal when none exists", async () => {
    const created = {
      id: 1,
      type: "weekly",
      target: 10,
      periodStart: "2026-03-16",
    };
    // First await: select existing → empty (not found)
    // Second await: insert returning → [created]
    (db as any)._queueResult([], [created]);

    const { POST } = await import("@/app/api/goals/route");
    const req = new NextRequest("http://localhost:3000/api/goals", {
      method: "POST",
      body: JSON.stringify({
        type: "weekly",
        target: 10,
        periodStart: "2026-03-16",
      }),
    });
    const res = await POST(req);
    const data = await res.json();

    expect(res.status).toBe(201);
    expect(data.target).toBe(10);
  });

  it("updates existing goal (upsert)", async () => {
    const existing = {
      id: 1,
      type: "weekly",
      target: 5,
      periodStart: "2026-03-16",
    };
    const updated = { ...existing, target: 15 };
    // First await: select existing → [existing] (found)
    // Second await: update returning → [updated]
    (db as any)._queueResult([existing], [updated]);

    const { POST } = await import("@/app/api/goals/route");
    const req = new NextRequest("http://localhost:3000/api/goals", {
      method: "POST",
      body: JSON.stringify({
        type: "weekly",
        target: 15,
        periodStart: "2026-03-16",
      }),
    });
    const res = await POST(req);
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.target).toBe(15);
  });

  it("throws on invalid JSON body", async () => {
    const { POST } = await import("@/app/api/goals/route");
    const req = new NextRequest("http://localhost:3000/api/goals", {
      method: "POST",
      body: "not json",
      headers: { "content-type": "application/json" },
    });

    await expect(POST(req)).rejects.toThrow();
  });
});
