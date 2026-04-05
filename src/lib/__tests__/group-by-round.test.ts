import { describe, it, expect } from "vitest";
import { groupByRound } from "@/lib/group-by-round";
import type { StepData, Message } from "@/lib/group-by-round";

const step = (id: number, step_type: string, round: number, status = "completed"): StepData => ({
  id, step_type, status, result: "{}", version: 1, round_number: round,
});
const msg = (role: "user" | "assistant", content: string, round: number): Message => ({
  role, content, round_number: round,
});

describe("groupByRound", () => {
  it("groups initial run as round 0 with no chat bubbles", () => {
    const rounds = groupByRound(
      [step(1, "jd_analysis", 0), step(2, "rewrite", 0)],
      [],
    );
    expect(rounds).toHaveLength(1);
    expect(rounds[0].round_number).toBe(0);
    expect(rounds[0].user_message).toBeNull();
    expect(rounds[0].ack_message).toBeNull();
    expect(rounds[0].steps.map((s) => s.step_type)).toEqual(["jd_analysis", "rewrite"]);
  });

  it("groups follow-up round with user and ack messages", () => {
    const rounds = groupByRound(
      [step(1, "jd_analysis", 0), step(2, "rewrite", 0), step(3, "rewrite", 1)],
      [msg("user", "more leadership", 1), msg("assistant", "Sure.", 1)],
    );
    expect(rounds).toHaveLength(2);
    expect(rounds[1].round_number).toBe(1);
    expect(rounds[1].user_message?.content).toBe("more leadership");
    expect(rounds[1].ack_message?.content).toBe("Sure.");
    expect(rounds[1].steps).toHaveLength(1);
    expect(rounds[1].steps[0].step_type).toBe("rewrite");
  });

  it("sorts steps inside a round in canonical order", () => {
    const rounds = groupByRound(
      [
        step(4, "rewrite", 0),
        step(2, "gap_analysis", 0),
        step(1, "jd_analysis", 0),
        step(3, "suggestions", 0),
      ],
      [],
    );
    expect(rounds[0].steps.map((s) => s.step_type)).toEqual([
      "jd_analysis", "gap_analysis", "suggestions", "rewrite",
    ]);
  });

  it("returns empty array when no steps and no messages", () => {
    expect(groupByRound([], [])).toEqual([]);
  });

  it("renders a chat-only round when steps are absent for round N", () => {
    const rounds = groupByRound(
      [step(1, "rewrite", 0)],
      [msg("user", "hi", 1), msg("assistant", "Nothing to change.", 1)],
    );
    expect(rounds).toHaveLength(2);
    expect(rounds[1].steps).toEqual([]);
    expect(rounds[1].user_message?.content).toBe("hi");
  });

  it("ignores an unexpected step_type", () => {
    const rounds = groupByRound([step(1, "unknown_step" as string, 0)], []);
    expect(rounds[0].steps).toEqual([]);
  });
});
