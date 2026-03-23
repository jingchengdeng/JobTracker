import { Card, CardContent } from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: string | number;
  color?: string; // CSS color for the value
}

export function StatCard({ label, value, color }: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center p-6">
        <p className="text-3xl font-extrabold" style={color ? { color } : undefined}>
          {value}
        </p>
        <p className="text-sm text-muted-foreground mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}
