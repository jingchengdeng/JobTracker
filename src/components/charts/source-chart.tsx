"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const SOURCE_COLORS: Record<string, string> = {
  linkedin: "#0a66c2",
  indeed: "#2164f3",
  company_site: "#6366f1",
  referral: "#22c55e",
  other: "#f59e0b",
};

const SOURCE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  company_site: "Company",
  referral: "Referral",
  other: "Other",
};

interface SourceChartProps {
  data: { source: string; count: number }[];
}

export function SourceChart({ data }: SourceChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    label: SOURCE_LABELS[d.source] ?? d.source,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Applications by Source</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
          >
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={64}
              tick={{ fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "transparent" }}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={SOURCE_COLORS[entry.source] ?? "#6366f1"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
