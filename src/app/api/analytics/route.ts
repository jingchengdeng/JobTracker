import { NextResponse } from "next/server";
import { db } from "@/db";
import { jobs, goals } from "@/db/schema";
import { sql, and, gte, lt, count } from "drizzle-orm";

export async function GET() {
  // Total by status
  const byStatus = db
    .select({
      status: jobs.status,
      count: count(),
    })
    .from(jobs)
    .groupBy(jobs.status)
    .all();

  // Total by source
  const bySource = db
    .select({
      source: jobs.source,
      count: count(),
    })
    .from(jobs)
    .where(sql`${jobs.source} IS NOT NULL`)
    .groupBy(jobs.source)
    .all();

  // Applications per week (last 12 weeks)
  const byWeek = db
    .select({
      week: sql<string>`strftime('%Y-%W', ${jobs.dateApplied})`.as("week"),
      count: count(),
    })
    .from(jobs)
    .where(
      and(
        sql`${jobs.dateApplied} IS NOT NULL`,
        gte(jobs.dateApplied, sql`date('now', '-84 days')`)
      )
    )
    .groupBy(sql`strftime('%Y-%W', ${jobs.dateApplied})`)
    .orderBy(sql`week`)
    .all();

  // Salary distribution (buckets of 20k)
  const salaryDist = db
    .select({
      bucket: sql<number>`(${jobs.salaryMin} / 20000) * 20000`.as("bucket"),
      count: count(),
    })
    .from(jobs)
    .where(sql`${jobs.salaryMin} IS NOT NULL`)
    .groupBy(sql`bucket`)
    .orderBy(sql`bucket`)
    .all();

  // Total counts
  const totalApplied = byStatus.reduce((sum, s) => sum + s.count, 0);
  const totalInterviews =
    byStatus.find((s) => s.status === "interview")?.count || 0;
  const totalOffers = byStatus.find((s) => s.status === "offer")?.count || 0;
  const totalGhosted =
    byStatus.find((s) => s.status === "ghosted")?.count || 0;
  const responded = totalApplied - totalGhosted;
  const responseRate =
    totalApplied > 0 ? Math.round((responded / totalApplied) * 100) : 0;

  // Goal progress — compute period end in JS, not SQL
  const allGoals = db.select().from(goals).all();
  const goalProgress = allGoals.map((goal) => {
    const start = new Date(goal.periodStart);
    let end: Date;
    if (goal.type === "weekly") {
      end = new Date(start);
      end.setDate(end.getDate() + 7);
    } else {
      end = new Date(start);
      end.setMonth(end.getMonth() + 1);
    }
    const periodEnd = end.toISOString().split("T")[0];

    const applied = db
      .select({ count: count() })
      .from(jobs)
      .where(
        and(
          sql`${jobs.dateApplied} IS NOT NULL`,
          gte(jobs.dateApplied, goal.periodStart),
          lt(jobs.dateApplied, periodEnd)
        )
      )
      .get();

    return {
      ...goal,
      current: applied?.count || 0,
    };
  });

  return NextResponse.json({
    byStatus,
    bySource,
    byWeek,
    salaryDistribution: salaryDist,
    totalApplied,
    totalInterviews,
    totalOffers,
    responseRate,
    goalProgress,
  });
}
