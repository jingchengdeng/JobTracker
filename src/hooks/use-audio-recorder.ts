"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseAudioRecorderReturn {
  isRecording: boolean;
  micPermission: "granted" | "denied" | "prompt";
  startRecording: () => void;
  stopRecording: () => void;
}

export function useAudioRecorder(
  onAudioReady: (blob: Blob) => void,
  enabled: boolean = true,
): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt">("prompt");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // Request mic permission on mount
  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        setMicPermission("granted");
      })
      .catch(() => setMicPermission("denied"));

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const startRecording = useCallback(async () => {
    if (!enabled) return;

    // Re-acquire stream if tracks are dead
    if (!streamRef.current || streamRef.current.getTracks().some((t) => t.readyState === "ended")) {
      try {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        setMicPermission("denied");
        return;
      }
    }

    chunksRef.current = [];
    try {
      const recorder = new MediaRecorder(streamRef.current, { mimeType: "audio/webm;codecs=opus" });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        if (blob.size > 0) onAudioReady(blob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      // Stream went bad between check and use — will retry on next keypress
    }
  }, [enabled, onAudioReady]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  // Spacebar push-to-talk
  useEffect(() => {
    if (!enabled || micPermission !== "granted") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        startRecording();
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        stopRecording();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [enabled, micPermission, startRecording, stopRecording]);

  return { isRecording, micPermission, startRecording, stopRecording };
}
