"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";

interface SalaryChartProps {
  data: { bucket: number; count: number }[];
}

function formatSalaryLabel(bucket: number): string {
  return `$${bucket / 1000}k`;
}

export function SalaryChart({ data }: SalaryChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    label: formatSalaryLabel(d.bucket),
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Salary Distribution</CardTitle>
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
              isAnimationActive={false}
              formatter={(value) => [value, "Jobs"]}
              cursor={{ fill: "rgba(16,185,129,0.06)" }}
              contentStyle={{
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(30,27,75,0.95)",
                color: "#e0e7ff",
                fontSize: "12px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
              }}
            />
            <defs>
              <linearGradient id="salaryGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
            </defs>
            <Bar dataKey="count" fill="url(#salaryGradient)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
