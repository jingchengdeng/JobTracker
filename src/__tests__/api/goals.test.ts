import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/db", () => {
  const createChain = () => {
    const chain: Record<string, any> = {};
    const methods = [
      "select",
      "from",
      "where",
      "insert",
      "update",
      "set",
      "values",
      "returning",
    ];
    for (const m of methods) {
      chain[m] = vi.fn(() => chain);
    }
    chain.get = vi.fn(() => null);
    chain.all = vi.fn(() => []);
    return chain;
  };

  return { db: createChain() };
});

const { db } = await import("@/db");

describe("GET /api/goals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns all goals", async () => {
    const goalsList = [
      { id: 1, type: "weekly", target: 5, periodStart: "2026-03-16" },
    ];
    (db.select().from({} as any) as any).all.mockReturnValue(goalsList);

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
    // First .get() call returns null (no existing), second returns the created goal
    const chain = db.select().from({} as any);
    (chain as any).get.mockReturnValueOnce(null).mockReturnValueOnce(created);

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
    (db.select().from({} as any).where({} as any) as any).get.mockReturnValue(
      existing
    );

    const updated = { ...existing, target: 15 };
    (db as any).update().set().where().returning().get.mockReturnValue(updated);

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
});
