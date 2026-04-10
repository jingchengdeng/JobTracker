import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb(), dbReady: Promise.resolve() };
});

const { db } = await import("@/db");

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("GET /api/jobs/[id]", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns a job when found", async () => {
    const job = { id: 1, title: "Dev", company: "Acme" };
    (db as any)._queueResult([job]);

    const { GET } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/1");
    const res = await GET(req, makeParams("1"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(job);
  });

  it("returns 404 when not found", async () => {
    (db as any)._queueResult([]);

    const { GET } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/999");
    const res = await GET(req, makeParams("999"));

    expect(res.status).toBe(404);
  });
});

describe("PUT /api/jobs/[id]", () => {
  beforeEach(() => vi.clearAllMocks());

  it("updates and returns the job", async () => {
    const updated = { id: 1, title: "Senior Dev", company: "Acme" };
    (db as any)._queueResult([updated]);

    const { PUT } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/1", {
      method: "PUT",
      body: JSON.stringify({ title: "Senior Dev" }),
    });
    const res = await PUT(req, makeParams("1"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.title).toBe("Senior Dev");
  });

  it("returns 404 when job doesnt exist", async () => {
    (db as any)._queueResult([]);

    const { PUT } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/999", {
      method: "PUT",
      body: JSON.stringify({ title: "X" }),
    });
    const res = await PUT(req, makeParams("999"));

    expect(res.status).toBe(404);
  });
});

describe("DELETE /api/jobs/[id]", () => {
  beforeEach(() => vi.clearAllMocks());

  it("deletes and returns success", async () => {
    const deleted = { id: 1, title: "Dev" };
    (db as any)._queueResult([deleted]);

    const { DELETE } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/1", {
      method: "DELETE",
    });
    const res = await DELETE(req, makeParams("1"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data.success).toBe(true);
  });

  it("returns 404 when job doesnt exist", async () => {
    (db as any)._queueResult([]);

    const { DELETE } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/999", {
      method: "DELETE",
    });
    const res = await DELETE(req, makeParams("999"));

    expect(res.status).toBe(404);
  });
});
