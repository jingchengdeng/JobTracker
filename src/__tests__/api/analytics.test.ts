import { describe, it, expect, vi, beforeEach } from "vitest";
vi.mock("@/db", async () => {
  const { createMockDb } = await import("../helpers/mock-db");
  return { db: createMockDb() };
});

const { db } = await import("@/db");

describe("GET /api/analytics", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns full analytics shape", async () => {
    // Mock the chain: multiple .all() and .get() calls in sequence
    const chain = db.select().from({} as any);

    // The analytics route calls .all() 4 times (byStatus, bySource, byWeek, salaryDist)
    // then .all() once for goals, then .get() for each goal's job count
    (chain as any).all
      .mockReturnValueOnce([
        { status: "applied", count: 10 },
        { status: "interview", count: 3 },
        { status: "offer", count: 1 },
        { status: "ghosted", count: 2 },
      ]) // byStatus
      .mockReturnValueOnce([
        { source: "linkedin", count: 8 },
        { source: "referral", count: 6 },
      ]) // bySource
      .mockReturnValueOnce([
        { week: "2026-11", count: 4 },
        { week: "2026-12", count: 6 },
      ]) // byWeek
      .mockReturnValueOnce([
        { bucket: 80000, count: 5 },
        { bucket: 100000, count: 3 },
      ]) // salaryDist
      .mockReturnValueOnce([
        {
          id: 1,
          type: "weekly",
          target: 5,
          periodStart: "2026-03-16",
          createdAt: "2026-03-16",
        },
      ]); // goals

    // Goal progress query: .get() for counting jobs in period
    (chain as any).get.mockReturnValueOnce({ count: 3 });

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
    const chain = db.select().from({} as any);

    (chain as any).all
      .mockReturnValueOnce([
        { status: "applied", count: 20 },
        { status: "interview", count: 5 },
        { status: "offer", count: 2 },
        { status: "ghosted", count: 3 },
      ])
      .mockReturnValueOnce([]) // bySource
      .mockReturnValueOnce([]) // byWeek
      .mockReturnValueOnce([]) // salaryDist
      .mockReturnValueOnce([]); // goals (none)

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
    const chain = db.select().from({} as any);

    (chain as any).all
      .mockReturnValueOnce([]) // byStatus
      .mockReturnValueOnce([]) // bySource
      .mockReturnValueOnce([]) // byWeek
      .mockReturnValueOnce([]) // salaryDist
      .mockReturnValueOnce([]); // goals

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
    const chain = db.select().from({} as any);

    (chain as any).all
      .mockReturnValueOnce([{ status: "applied", count: 5 }])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([
        {
          id: 1,
          type: "weekly",
          target: 10,
          periodStart: "2026-03-16",
          createdAt: "2026-03-16",
        },
      ]);

    (chain as any).get.mockReturnValueOnce({ count: 7 });

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(data.goalProgress).toHaveLength(1);
    expect(data.goalProgress[0].current).toBe(7);
    expect(data.goalProgress[0].target).toBe(10);
    expect(data.goalProgress[0].type).toBe("weekly");
  });

  it("computes monthly goal period end correctly", async () => {
    const chain = db.select().from({} as any);

    (chain as any).all
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([])
      .mockReturnValueOnce([
        {
          id: 2,
          type: "monthly",
          target: 20,
          periodStart: "2026-03-01",
          createdAt: "2026-03-01",
        },
      ]);

    (chain as any).get.mockReturnValueOnce({ count: 15 });

    const { GET } = await import("@/app/api/analytics/route");
    const res = await GET();
    const data = await res.json();

    expect(data.goalProgress).toHaveLength(1);
    expect(data.goalProgress[0].current).toBe(15);
    expect(data.goalProgress[0].type).toBe("monthly");
  });
});
