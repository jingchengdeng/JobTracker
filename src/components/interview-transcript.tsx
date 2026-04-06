"use client";

import { useEffect, useRef } from "react";
import type { InterviewTurn } from "@/lib/types";

interface InterviewTranscriptProps {
  turns: InterviewTurn[];
  streamingText: string | null;
}

export function InterviewTranscript({ turns, streamingText }: InterviewTranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streamingText]);

  return (
    <div className="flex-1 overflow-y-auto space-y-3 p-2">
      {turns.map((turn) => (
        <div key={turn.id} className={turn.role === "candidate" ? "ml-10" : ""}>
          <p className="text-xs text-muted-foreground mb-1">
            {turn.role === "interviewer" ? "Interviewer" : "You"}
          </p>
          <div className={`rounded-lg p-3 text-sm ${
            turn.role === "interviewer" ? "bg-muted" : "bg-primary/10 ml-auto"
          }`}>
            {turn.text}
          </div>
        </div>
      ))}
      {streamingText && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">Interviewer</p>
          <div className="rounded-lg bg-muted p-3 text-sm">
            {streamingText}<span className="animate-pulse">|</span>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
