"use client";

import { StepCard } from "@/components/step-card";
import type { Round } from "@/lib/group-by-round";

interface RoundBlockProps {
  round: Round;
  expandedStepIds: Set<number>;
  onToggleStep: (stepId: number) => void;
  thinking?: boolean;
}

export function RoundBlock({ round, expandedStepIds, onToggleStep, thinking }: RoundBlockProps) {
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
      {round.ack_message ? (
        <div className="max-w-[80%] rounded bg-muted px-3 py-2 text-sm text-muted-foreground">
          <span className="font-medium">AI:</span> {round.ack_message.content}
        </div>
      ) : thinking ? (
        <div className="max-w-[80%] rounded bg-muted px-3 py-2 text-sm text-muted-foreground">
          <span className="font-medium">AI:</span>{" "}
          <span className="inline-flex items-center gap-1">
            <span className="animate-pulse">Thinking</span>
            <span className="inline-flex gap-0.5">
              <span className="animate-bounce [animation-delay:0ms]">.</span>
              <span className="animate-bounce [animation-delay:150ms]">.</span>
              <span className="animate-bounce [animation-delay:300ms]">.</span>
            </span>
          </span>
        </div>
      ) : null}
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
