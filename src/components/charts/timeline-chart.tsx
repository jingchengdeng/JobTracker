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
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={chartData}
            margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
          >
            <XAxis
              dataKey="label"
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis hide />
            <Tooltip
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "rgba(59,130,246,0.06)" }}
              contentStyle={{
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(30,27,75,0.85)",
                backdropFilter: "blur(20px)",
                color: "#e0e7ff",
                fontSize: "12px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
              }}
            />
            <defs>
              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#6366f1" />
              </linearGradient>
            </defs>
            <Bar dataKey="count" fill="url(#barGradient)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
