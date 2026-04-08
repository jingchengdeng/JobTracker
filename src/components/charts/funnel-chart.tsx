"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";

const STATUS_COLORS: Record<string, string> = {
  saved: "#64748b",
  applied: "#3b82f6",
  phone_screen: "#0ea5e9",
  interview: "#10b981",
  offer: "#8b5cf6",
  accepted: "#22c55e",
  rejected: "#ef4444",
  withdrawn: "#f59e0b",
  ghosted: "#94a3b8",
};

const STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  applied: "Applied",
  phone_screen: "Screen",
  interview: "Interview",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  ghosted: "Ghosted",
};

interface FunnelChartProps {
  data: { status: string; count: number }[];
}

export function FunnelChart({ data }: FunnelChartProps) {
  const chartData = data.map((d) => ({
    ...d,
    label: STATUS_LABELS[d.status] ?? d.status,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Applications by Status</CardTitle>
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
              width={72}
              tick={{ fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              isAnimationActive={false}
              formatter={(value) => [value, "Applications"]}
              cursor={{ fill: "transparent" }}
              contentStyle={{
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(30,27,75,0.95)",
                color: "#e0e7ff",
                fontSize: "12px",
                boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
              }}
            />
            <Bar dataKey="count" radius={[0, 6, 6, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={STATUS_COLORS[entry.status] ?? "#64748b"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
