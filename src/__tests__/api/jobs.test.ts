import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb(), dbReady: Promise.resolve() };
});

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
    (db as any)._queueResult(jobs);

    const { GET } = await import("@/app/api/jobs/route");
    const res = await GET(makeRequest("/api/jobs"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(jobs);
  });

  it("applies status filter", async () => {
    const { GET } = await import("@/app/api/jobs/route");
    await GET(makeRequest("/api/jobs?status=applied"));

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
    (db as any)._queueResult([newJob]);

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

  it("throws on invalid JSON body", async () => {
    const { POST } = await import("@/app/api/jobs/route");
    const req = new NextRequest("http://localhost:3000/api/jobs", {
      method: "POST",
      body: "not json",
      headers: { "content-type": "application/json" },
    });

    await expect(POST(req)).rejects.toThrow();
  });
});
