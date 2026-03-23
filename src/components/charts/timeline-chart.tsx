"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

interface TimelineChartProps {
  data: { week: string; count: number }[];
}

function formatWeekLabel(week: string): string {
  const match = week.match(/\d{4}-(\d+)$/);
  if (match) {
    return `W${match[1]}`;
  }
  return week;
}

export function TimelineChart({ data }: TimelineChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    label: formatWeekLabel(d.week),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Applications per Week</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={chartData}
            margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
          >
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "rgba(99,102,241,0.08)" }}
            />
            <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
