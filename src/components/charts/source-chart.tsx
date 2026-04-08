"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const SOURCE_COLORS: Record<string, string> = {
  linkedin: "#0a66c2",
  indeed: "#3b82f6",
  company_site: "#8b5cf6",
  referral: "#10b981",
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
        <ResponsiveContainer width="100%" height={220}>
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
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "transparent" }}
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
            <Bar dataKey="count" radius={[0, 6, 6, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={SOURCE_COLORS[entry.source] ?? "#3b82f6"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
