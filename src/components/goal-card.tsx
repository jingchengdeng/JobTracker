"use client";

import { useState } from "react";
import { Target } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface GoalCardProps {
  goal: {
    id: number;
    type: string;
    target: number;
    periodStart: string;
    current: number;
  } | null;
  onSave: (data: { type: string; target: number; periodStart: string }) => void;
}

export function GoalCard({ goal, onSave }: GoalCardProps) {
  const [editing, setEditing] = useState(false);
  const [type, setType] = useState(goal?.type ?? "weekly");
  const [target, setTarget] = useState(goal?.target?.toString() ?? "");
  const [periodStart, setPeriodStart] = useState(goal?.periodStart ?? "");

  const showForm = !goal || editing;

  function handleSave() {
    onSave({ type, target: Number(target), periodStart });
    setEditing(false);
  }

  if (showForm) {
    return (
      <Card className="col-span-2 border-primary bg-gradient-to-br from-background to-primary/5">
        <CardContent className="p-6 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Target className="size-5 text-primary" />
            <span className="font-semibold text-base">Set Your Goal</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">Type</label>
              <Select value={type} onValueChange={(v) => v && setType(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">Target</label>
              <Input
                type="number"
                min={1}
                placeholder="e.g. 10"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">Period Start</label>
              <Input
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={!target || !periodStart}>
              Save
            </Button>
            {goal && (
              <Button variant="outline" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  const pct = Math.min(100, Math.round((goal.current / goal.target) * 100));
  const remaining = Math.max(0, goal.target - goal.current);
  const periodLabel = goal.type === "weekly" ? "week" : "month";

  let message: string;
  if (pct >= 100) {
    message = "Goal reached! Keep it up!";
  } else if (pct >= 75) {
    message = "Almost there!";
  } else if (pct >= 50) {
    message = `${remaining} more to go!`;
  } else {
    message = `${remaining} more to hit your target`;
  }

  return (
    <Card className="col-span-2 border-primary bg-gradient-to-br from-background to-primary/5">
      <CardContent className="p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="size-5 text-primary" />
            <span className="font-semibold text-base capitalize">
              {goal.type} Goal
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            Edit
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">
          Apply to {goal.target} jobs this {periodLabel}
        </p>
        {/* Progress bar */}
        <div className="relative h-7 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full"
            style={{
              width: `${pct}%`,
              background: "linear-gradient(to right, hsl(var(--primary)), #a855f7)",
              transition: "width 0.4s ease",
            }}
          />
          <span className="absolute inset-0 flex items-center justify-center text-xs font-semibold">
            {goal.current} / {goal.target}
          </span>
        </div>
        <p className="text-sm font-medium text-primary">{message}</p>
      </CardContent>
    </Card>
  );
}
