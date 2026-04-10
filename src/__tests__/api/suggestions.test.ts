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

describe("GET /api/jobs/suggestions", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns suggestions for a valid field", async () => {
    (db as any)._queueResult([{ value: "Google" }, { value: "Meta" }]);

    const { GET } = await import("@/app/api/jobs/suggestions/route");
    const res = await GET(makeRequest("/api/jobs/suggestions?field=company"));
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(["Google", "Meta"]);
  });

  it("returns 400 for missing field", async () => {
    const { GET } = await import("@/app/api/jobs/suggestions/route");
    const res = await GET(makeRequest("/api/jobs/suggestions"));

    expect(res.status).toBe(400);
  });

  it("returns 400 for disallowed field", async () => {
    const { GET } = await import("@/app/api/jobs/suggestions/route");
    const res = await GET(
      makeRequest("/api/jobs/suggestions?field=status")
    );

    expect(res.status).toBe(400);
  });

  it("accepts all allowed fields", async () => {
    const allowed = [
      "company",
      "location",
      "contact_name",
      "contact_email",
      "resume_version",
    ];

    const { GET } = await import("@/app/api/jobs/suggestions/route");

    for (const field of allowed) {
      const res = await GET(
        makeRequest(`/api/jobs/suggestions?field=${field}`)
      );
      expect(res.status).toBe(200);
    }
  });
});
