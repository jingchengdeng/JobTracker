"use client";

import { useEffect, useState } from "react";
import { GoalCard } from "@/components/goal-card";
import { StatCard } from "@/components/stat-card";
import { FunnelChart } from "@/components/charts/funnel-chart";
import { TimelineChart } from "@/components/charts/timeline-chart";
import { SourceChart } from "@/components/charts/source-chart";
import { SalaryChart } from "@/components/charts/salary-chart";

interface GoalProgress {
  id: number;
  type: string;
  target: number;
  periodStart: string;
  current: number;
}

interface AnalyticsData {
  byStatus: { status: string; count: number }[];
  bySource: { source: string; count: number }[];
  byWeek: { week: string; count: number }[];
  salaryDistribution: { bucket: number; count: number }[];
  totalApplied: number;
  totalInterviews: number;
  totalOffers: number;
  responseRate: number;
  goalProgress: GoalProgress[];
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  async function fetchAnalytics() {
    const res = await fetch("/api/analytics");
    const json = await res.json();
    setData(json);
    setLoading(false);
  }

  useEffect(() => {
    fetchAnalytics();
  }, []);

  async function handleGoalSave(goalData: {
    type: string;
    target: number;
    periodStart: string;
  }) {
    await fetch("/api/goals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(goalData),
    });
    await fetchAnalytics();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Loading analytics...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Failed to load analytics.</p>
      </div>
    );
  }

  const weeklyGoal = data.goalProgress.find((g) => g.type === "weekly") ?? null;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold">Analytics &amp; Goals</h1>

      {/* Top row: 5-column grid */}
      <div className="grid grid-cols-5 gap-4">
        <GoalCard goal={weeklyGoal} onSave={handleGoalSave} />
        <StatCard label="Total Applied" value={data.totalApplied} color="#6366f1" />
        <StatCard label="Interviews" value={data.totalInterviews} color="#22c55e" />
        <StatCard label="Response Rate" value={`${data.responseRate}%`} color="#f59e0b" />
      </div>

      {/* Chart grid: 2x2 */}
      <div className="grid grid-cols-2 gap-4">
        <FunnelChart data={data.byStatus} />
        <TimelineChart data={data.byWeek} />
        <SourceChart data={data.bySource} />
        <SalaryChart data={data.salaryDistribution} />
      </div>
    </div>
  );
}
