"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";

interface InterviewControlsProps {
  startedAt: string | null;
  durationMinutes: number;
  onPause: () => void;
  onEnd: () => void;
  isPaused: boolean;
  onResume: () => void;
}

export function InterviewControls({
  startedAt, durationMinutes, onPause, onEnd, isPaused, onResume,
}: InterviewControlsProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (isPaused) return;
    const startTime = startedAt
      ? new Date(startedAt.endsWith("Z") ? startedAt : startedAt + "Z").getTime()
      : Date.now();
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startedAt, isPaused]);

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <div className="flex items-center justify-between border-b px-3 py-2">
      <span className="text-xs text-muted-foreground">
        {String(mins).padStart(2, "0")}:{String(secs).padStart(2, "0")} / {durationMinutes}:00
      </span>
      <div className="flex gap-2">
        {isPaused ? (
          <Button variant="outline" size="sm" onClick={onResume}>Resume</Button>
        ) : (
          <Button variant="outline" size="sm" onClick={onPause}>Pause</Button>
        )}
        <Button variant="destructive" size="sm" onClick={onEnd}>End</Button>
      </div>
    </div>
  );
}
