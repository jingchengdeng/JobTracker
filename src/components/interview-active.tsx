"use client";

import { InterviewTranscript } from "@/components/interview-transcript";
import { InterviewControls } from "@/components/interview-controls";
import { AudioRecorder } from "@/components/audio-recorder";
import type { InterviewTurn } from "@/lib/types";

interface InterviewActiveProps {
  turns: InterviewTurn[];
  streamingText: string | null;
  startedAt: string | null;
  durationMinutes: number;
  isPaused: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  micPermission: "granted" | "denied" | "prompt";
  connectionStatus: string;
  onPause: () => void;
  onResume: () => void;
  onEnd: () => void;
  onTextSubmit: (text: string) => void;
}

export function InterviewActive({
  turns, streamingText, startedAt, durationMinutes, isPaused,
  isRecording, isProcessing, micPermission, connectionStatus,
  onPause, onResume, onEnd, onTextSubmit,
}: InterviewActiveProps) {
  return (
    <div className="flex h-full flex-col rounded-lg border">
      <InterviewControls
        startedAt={startedAt}
        durationMinutes={durationMinutes}
        onPause={onPause}
        onEnd={onEnd}
        isPaused={isPaused}
        onResume={onResume}
      />
      {connectionStatus !== "connected" && (
        <div className="bg-yellow-500/10 px-3 py-1 text-center text-xs text-yellow-600">
          {connectionStatus === "reconnecting" ? "Reconnecting..." : "Disconnected"}
        </div>
      )}
      <InterviewTranscript turns={turns} streamingText={streamingText} />
      <AudioRecorder
        isRecording={isRecording}
        micPermission={micPermission}
        onTextSubmit={onTextSubmit}
        isProcessing={isProcessing}
      />
    </div>
  );
}
