"use client";

import { StepCard } from "@/components/step-card";
import type { Round } from "@/lib/group-by-round";

interface RoundBlockProps {
  round: Round;
  expandedStepIds: Set<number>;
  onToggleStep: (stepId: number) => void;
}

export function RoundBlock({ round, expandedStepIds, onToggleStep }: RoundBlockProps) {
  const label = round.round_number === 0 ? "Initial analysis" : `Round ${round.round_number}`;

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      {round.user_message && (
        <div className="ml-auto max-w-[80%] rounded bg-primary/10 px-3 py-2 text-sm">
          <span className="font-medium">You:</span> {round.user_message.content}
        </div>
      )}
      {round.ack_message && (
        <div className="max-w-[80%] rounded bg-muted px-3 py-2 text-sm text-muted-foreground">
          <span className="font-medium">AI:</span> {round.ack_message.content}
        </div>
      )}
      {round.steps.map((step) => (
        <StepCard
          key={step.id}
          step={step}
          expanded={expandedStepIds.has(step.id)}
          onToggle={() => onToggleStep(step.id)}
        />
      ))}
    </div>
  );
}
