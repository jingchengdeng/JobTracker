import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

// Mock the db module — every test controls what the db calls return
vi.mock("@/db", () => {
  // Mocked data that tests can override
  let _resolveData: unknown[] = [];

  const createChain = () => {
    const chain: Record<string, any> = {};
    const methods = [
      "select",
      "from",
      "where",
      "orderBy",
      "groupBy",
      "insert",
      "update",
      "delete",
      "set",
      "values",
      "returning",
      "$dynamic",
    ];
    for (const m of methods) {
      chain[m] = vi.fn(() => chain);
    }
    chain.get = vi.fn(() => null);
    chain.all = vi.fn(() => []);
    // Make chain thenable so `await query` works (drizzle queries are awaitable)
    chain.then = vi.fn((resolve: any) => resolve(_resolveData));
    chain._setResolveData = (data: unknown[]) => {
      _resolveData = data;
    };
    return chain;
  };

  const chain = createChain();
  return { db: chain };
});

// Must import after mock setup
const { db } = await import("@/db");

function makeRequest(url: string) {
  return new NextRequest(new URL(url, "http://localhost:3000"));
}

describe("GET /api/jobs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns jobs list", async () => {
    const jobs = [
      { id: 1, title: "Dev", company: "Acme", status: "applied" },
    ];
    // Set what `await query` resolves to
    (db as any)._setResolveData(jobs);

    const { GET } = await import("@/app/api/jobs/route");
    const res = await GET(makeRequest("/api/jobs"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(jobs);
  });

  it("applies status filter", async () => {
    const { GET } = await import("@/app/api/jobs/route");
    await GET(makeRequest("/api/jobs?status=applied"));

    // The where method should have been called (filter applied)
    const chain = db.select().from({} as any);
    expect(chain.where).toHaveBeenCalled();
  });

  it("applies search filter", async () => {
    const { GET } = await import("@/app/api/jobs/route");
    await GET(makeRequest("/api/jobs?search=google"));

    const chain = db.select().from({} as any);
    expect(chain.where).toHaveBeenCalled();
  });
});

describe("POST /api/jobs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a job and returns 201", async () => {
    const newJob = { id: 1, title: "Dev", company: "Acme", status: "saved" };
    (db as any).insert().values().returning().get.mockReturnValue(newJob);

    const { POST } = await import("@/app/api/jobs/route");
    const req = new NextRequest("http://localhost:3000/api/jobs", {
      method: "POST",
      body: JSON.stringify({ title: "Dev", company: "Acme" }),
    });
    const res = await POST(req);
    const data = await res.json();

    expect(res.status).toBe(201);
    expect(data).toEqual(newJob);
  });
});
