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
        <ResponsiveContainer width="100%" height={200}>
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
              formatter={(value) => [value, "Jobs"]}
              cursor={{ fill: "rgba(34,197,94,0.08)" }}
            />
            <Bar dataKey="count" fill="#22c55e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
