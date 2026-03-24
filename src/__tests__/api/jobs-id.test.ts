import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/db", () => {
  const createChain = (terminal?: unknown) => {
    const chain: Record<string, any> = {};
    const methods = [
      "select",
      "from",
      "where",
      "insert",
      "update",
      "delete",
      "set",
      "values",
      "returning",
    ];
    for (const m of methods) {
      chain[m] = vi.fn(() => chain);
    }
    chain.get = vi.fn(() => terminal ?? null);
    chain.all = vi.fn(() => terminal ?? []);
    return chain;
  };

  return { db: createChain() };
});

const { db } = await import("@/db");

function makeParams(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("GET /api/jobs/[id]", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns a job when found", async () => {
    const job = { id: 1, title: "Dev", company: "Acme" };
    (db.select().from({} as any).where({} as any) as any).get.mockReturnValue(
      job
    );

    const { GET } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/1");
    const res = await GET(req, makeParams("1"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(job);
  });

  it("returns 404 when not found", async () => {
    (db.select().from({} as any).where({} as any) as any).get.mockReturnValue(
      null
    );

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
    (db as any).update().set().where().returning().get.mockReturnValue(updated);

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
    (db as any).update().set().where().returning().get.mockReturnValue(null);

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
    (db as any).delete().where().returning().get.mockReturnValue(deleted);

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
    (db as any).delete().where().returning().get.mockReturnValue(null);

    const { DELETE } = await import("@/app/api/jobs/[id]/route");
    const req = new NextRequest("http://localhost:3000/api/jobs/999", {
      method: "DELETE",
    });
    const res = await DELETE(req, makeParams("999"));

    expect(res.status).toBe(404);
  });
});
