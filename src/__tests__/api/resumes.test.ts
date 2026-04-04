import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb() };
});

vi.mock("fs", () => ({
  existsSync: vi.fn(() => true),
  mkdirSync: vi.fn(),
  unlinkSync: vi.fn(),
  writeFileSync: vi.fn(),
}));

function makeRequest(url: string, options?: RequestInit) {
  return new NextRequest(new URL(url, "http://localhost:3000"), options);
}

describe("GET /api/resumes", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("returns a list of resumes", async () => {
    const { db } = await import("@/db");
    const mockResumes = [
      { id: 1, name: "Backend Resume", version: "v1", filePath: "data/resumes/1.pdf", fileType: "pdf", extractedText: null, createdAt: "2026-04-03" },
    ];
    (db as any).select().from({}).orderBy().all.mockReturnValue(mockResumes);

    const { GET } = await import("@/app/api/resumes/route");
    const res = await GET();
    const data = await res.json();

    expect(res.status).toBe(200);
    expect(data).toEqual(mockResumes);
  });
});

describe("DELETE /api/resumes/[id]", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("returns 404 for missing resume", async () => {
    const { db } = await import("@/db");
    (db as any).select().from({}).where().get.mockReturnValue(undefined);

    const { DELETE } = await import("@/app/api/resumes/[id]/route");
    const res = await DELETE(makeRequest("/api/resumes/999"), {
      params: Promise.resolve({ id: "999" }),
    });

    expect(res.status).toBe(404);
  });
});
