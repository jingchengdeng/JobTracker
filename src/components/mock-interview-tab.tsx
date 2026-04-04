"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Job } from "@/lib/types";

interface MockInterviewTabProps {
  job: Job;
}

const MOCK_SCORES = [
  { label: "Technical Depth", score: 78 },
  { label: "Communication", score: 85 },
  { label: "Structure", score: 72 },
];

const MOCK_FEEDBACK = [
  "Strong explanation of system design trade-offs, but could provide more concrete examples from past experience.",
  "Good use of the STAR method in behavioral answers. Consider adding more quantitative impact metrics.",
  "When discussing distributed systems, elaborate on failure modes and recovery strategies.",
  "Time management was good -- all questions answered within the allotted time.",
];

export function MockInterviewTab({ job }: MockInterviewTabProps) {
  return (
    <div className="space-y-4">
      <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 dark:text-amber-400">
        Demo -- mock data for preview
      </Badge>

      <Card className="p-4">
        <h3 className="mb-3 font-medium">Interview Setup</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm text-muted-foreground">Type</label>
            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" disabled>
              <option>Technical</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Difficulty</label>
            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" disabled>
              <option>Medium</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Duration</label>
            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" disabled>
              <option>30 minutes</option>
            </select>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Focus Area</label>
            <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" disabled>
              <option>System Design</option>
            </select>
          </div>
        </div>
        <Button className="mt-3" disabled>
          Start Interview
        </Button>
      </Card>

      <Card className="p-4">
        <h3 className="mb-3 font-medium">Interview Feedback (Sample)</h3>

        <div className="mb-4 grid grid-cols-3 gap-3">
          {MOCK_SCORES.map((item) => (
            <div key={item.label} className="rounded border p-3 text-center">
              <p className="text-2xl font-bold">{item.score}</p>
              <p className="text-xs text-muted-foreground">{item.label}</p>
            </div>
          ))}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium">Improvement Points</p>
          <ul className="space-y-2">
            {MOCK_FEEDBACK.map((point, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                {point}
              </li>
            ))}
          </ul>
        </div>
      </Card>
    </div>
  );
}
