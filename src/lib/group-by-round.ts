export interface StepData {
  id: number;
  step_type: string;
  status: string;
  result: string | null;
  version: number;
  round_number: number;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  round_number: number;
}

export interface Round {
  round_number: number;
  user_message: Message | null;
  ack_message: Message | null;
  steps: StepData[];
}

const CANONICAL_ORDER = ["jd_analysis", "gap_analysis", "suggestions", "rewrite"] as const;

export function groupByRound(steps: StepData[], messages: Message[]): Round[] {
  const roundNumbers = new Set<number>();
  for (const s of steps) roundNumbers.add(s.round_number);
  for (const m of messages) roundNumbers.add(m.round_number);

  const sorted = Array.from(roundNumbers).sort((a, b) => a - b);

  return sorted.map((n) => {
    const stepsForRound = steps
      .filter((s) => s.round_number === n && CANONICAL_ORDER.includes(s.step_type as typeof CANONICAL_ORDER[number]))
      .sort(
        (a, b) =>
          CANONICAL_ORDER.indexOf(a.step_type as typeof CANONICAL_ORDER[number]) -
          CANONICAL_ORDER.indexOf(b.step_type as typeof CANONICAL_ORDER[number]),
      );
    const msgsForRound = messages.filter((m) => m.round_number === n);
    return {
      round_number: n,
      user_message: msgsForRound.find((m) => m.role === "user") ?? null,
      ack_message: msgsForRound.find((m) => m.role === "assistant") ?? null,
      steps: stepsForRound,
    };
  });
}
