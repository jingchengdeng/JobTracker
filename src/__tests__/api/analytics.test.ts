import { describe, it, expect, vi, beforeEach } from "vitest";
vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb(), dbReady: Promise.resolve() };
});

const { db } = await import("@/db");

describe("GET /api/analytics", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns full analytics shape", async () => {
    (db as any)._queueResult(
      // await 1: byStatus
      [
        { status: "applied", count: 10 },
        { status: "interview", count: 3 },
        { status: "offer", count: 1 },
        { status: "ghosted", count: 2 },
      ],
      // await 2: bySource
      [
        { source: "linkedin", count: 8 },
        { source: "referral", count: 6 },
      ],
      // await 3: byWeek
      [
        { week: "2026-11", count: 4 },
        { week: "2026-12", count: 6 },
      ],
      // await 4: salaryDist
      [
        { bucket: 80000, count: 5 },
        { bucket: 100000, count: 3 },
      ],
      // await 5: allGoals
      [
        {
          id: 1,
          type: "weekly",
          target: 5,
          periodStart: "2026-03-16",
          createdAt: "2026-03-16",
        },
      ],
      // await 6: goal count query (destructured as [applied])
      [{ count: 3 }],
    );

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(res.status).toBe(200);

    // Shape checks
    expect(data).toHaveProperty("byStatus");
    expect(data).toHaveProperty("bySource");
    expect(data).toHaveProperty("byWeek");
    expect(data).toHaveProperty("salaryDistribution");
    expect(data).toHaveProperty("totalApplied");
    expect(data).toHaveProperty("totalInterviews");
    expect(data).toHaveProperty("totalOffers");
    expect(data).toHaveProperty("responseRate");
    expect(data).toHaveProperty("goalProgress");
  });

  it("calculates stats correctly from status counts", async () => {
    (db as any)._queueResult(
      [
        { status: "applied", count: 20 },
        { status: "interview", count: 5 },
        { status: "offer", count: 2 },
        { status: "ghosted", count: 3 },
      ],
      [], // bySource
      [], // byWeek
      [], // salaryDist
      [], // goals (none)
    );

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    // totalApplied = sum of all counts = 30
    expect(data.totalApplied).toBe(30);
    expect(data.totalInterviews).toBe(5);
    expect(data.totalOffers).toBe(2);
    // responseRate = (30 - 3 ghosted) / 30 = 90%
    expect(data.responseRate).toBe(90);
  });

  it("handles empty database gracefully", async () => {
    (db as any)._queueResult(
      [], // byStatus
      [], // bySource
      [], // byWeek
      [], // salaryDist
      [], // goals
    );

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(data.totalApplied).toBe(0);
    expect(data.totalInterviews).toBe(0);
    expect(data.totalOffers).toBe(0);
    expect(data.responseRate).toBe(0);
    expect(data.goalProgress).toEqual([]);
  });

  it("computes weekly goal period end correctly", async () => {
    (db as any)._queueResult(
      [{ status: "applied", count: 5 }],
      [], // bySource
      [], // byWeek
      [], // salaryDist
      [
        {
          id: 1,
          type: "weekly",
          target: 10,
          periodStart: "2026-03-16",
          createdAt: "2026-03-16",
        },
      ],
      [{ count: 7 }], // goal count
    );

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(data.goalProgress).toHaveLength(1);
    expect(data.goalProgress[0].current).toBe(7);
    expect(data.goalProgress[0].target).toBe(10);
    expect(data.goalProgress[0].type).toBe("weekly");
  });

  it("computes monthly goal period end correctly", async () => {
    (db as any)._queueResult(
      [], // byStatus
      [], // bySource
      [], // byWeek
      [], // salaryDist
      [
        {
          id: 2,
          type: "monthly",
          target: 20,
          periodStart: "2026-03-01",
          createdAt: "2026-03-01",
        },
      ],
      [{ count: 15 }], // goal count
    );

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(data.goalProgress).toHaveLength(1);
    expect(data.goalProgress[0].current).toBe(15);
    expect(data.goalProgress[0].type).toBe("monthly");
  });
});
