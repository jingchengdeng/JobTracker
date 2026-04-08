import { Send, Users, TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const ICONS = {
  send: Send,
  users: Users,
  "trending-up": TrendingUp,
} as const;

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: keyof typeof ICONS;
  color?: string;
}

export function StatCard({ label, value, icon, color }: StatCardProps) {
  const Icon = icon ? ICONS[icon] : null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-5">
        {Icon && (
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10">
            <Icon className="h-4 w-4 text-indigo-400" />
          </div>
        )}
        <p
          className="text-3xl font-bold tracking-tight"
          style={color ? { color } : undefined}
        >
          {value}
        </p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
