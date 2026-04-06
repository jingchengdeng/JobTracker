"use client";

interface AudioRecorderProps {
  isRecording: boolean;
  micPermission: "granted" | "denied" | "prompt";
  onTextSubmit: (text: string) => void;
  isProcessing: boolean;
}

import { useState } from "react";

export function AudioRecorder({ isRecording, micPermission, onTextSubmit, isProcessing }: AudioRecorderProps) {
  const [textInput, setTextInput] = useState("");

  return (
    <div className="border-t p-3">
      <div className="flex items-center gap-2">
        <input
          className="flex-1 rounded-md border bg-background px-3 py-2 text-sm"
          placeholder="Type a response (text fallback)..."
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && textInput.trim()) {
              onTextSubmit(textInput.trim());
              setTextInput("");
            }
          }}
          disabled={isProcessing}
        />
        <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 text-lg ${
          isRecording
            ? "animate-pulse border-red-500 bg-red-500/10"
            : micPermission === "granted"
              ? "border-muted-foreground"
              : "border-muted opacity-50"
        }`}>
          🎤
        </div>
      </div>
      <p className="mt-1 text-center text-xs text-muted-foreground">
        {micPermission === "denied"
          ? "Mic access denied -- use text input"
          : isProcessing
            ? "Processing..."
            : isRecording
              ? "Recording... release Space to send"
              : "Hold Space to talk"}
      </p>
    </div>
  );
}
