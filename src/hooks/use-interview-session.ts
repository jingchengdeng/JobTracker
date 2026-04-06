"use client";

import { useState, useCallback, useEffect } from "react";
import { useInterviewWebSocket } from "@/hooks/use-interview-websocket";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { useAudioPlayback } from "@/hooks/use-audio-playback";
import type { Job, InterviewTurn, InterviewSessionSummary } from "@/lib/types";

type Screen = "setup" | "planning" | "active" | "results" | "history";

interface StartConfig {
  interview_type: string;
  difficulty: string;
  duration_minutes: number;
  focus_area: string | null;
  resume_id: number | null;
  voice: string;
}

export function useInterviewSession(job: Job) {
  const [screen, setScreen] = useState<Screen>("setup");
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionConfig, setSessionConfig] = useState<{
    startedAt: string | null;
    durationMinutes: number;
    status: string;
  }>({
    startedAt: null,
    durationMinutes: 30,
    status: "planning",
  });
  const [results, setResults] = useState<Record<string, unknown> | null>(null);
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch session history
  const fetchSessions = useCallback(async () => {
    const res = await fetch(`/api/ai/interview/sessions?job_id=${job.id}`);
    if (res.ok) setSessions(await res.json());
  }, [job.id]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Audio playback
  const { isPlaying, queueChunk, clearQueue } = useAudioPlayback();

  // WebSocket
  const { status: wsStatus, sendAudio, sendText, sendEnd } = useInterviewWebSocket(
    wsUrl,
    (msg) => {
      if (msg.type === "connected") {
        setScreen("active");
        setSessionConfig((prev) => ({ ...prev, status: "active" }));
      } else if (msg.type === "transcript") {
        setTurns((prev) => [
          ...prev,
          {
            id: Date.now(),
            sessionId: sessionId!,
            turnNumber: prev.length + 1,
            role: "candidate",
            text: msg.text as string,
            audioDurationMs: null,
            planTopicRef: null,
            createdAt: new Date().toISOString(),
          },
        ]);
      } else if (msg.type === "interviewer_text" && msg.done) {
        setTurns((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            sessionId: sessionId!,
            turnNumber: prev.length + 1,
            role: "interviewer",
            text: msg.delta as string,
            audioDurationMs: null,
            planTopicRef: null,
            createdAt: new Date().toISOString(),
          },
        ]);
        setStreamingText(null);
        setIsProcessing(false);
      } else if (msg.type === "interviewer_text" && !msg.done) {
        setStreamingText((prev) => (prev || "") + (msg.delta as string));
      } else if (msg.type === "error") {
        setIsProcessing(false);
      }
    },
    (chunk) => queueChunk(chunk),
  );

  // Audio recorder
  const { isRecording, micPermission } = useAudioRecorder(
    (blob) => {
      setIsProcessing(true);
      sendAudio(blob);
    },
    screen === "active" && !isProcessing,
  );

  // Actions
  const startInterview = useCallback(
    async (config: StartConfig) => {
      setLoading(true);
      const res = await fetch("/api/ai/interview/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: job.id, ...config }),
      });
      if (!res.ok) {
        setLoading(false);
        return;
      }
      const data = await res.json();
      setSessionId(data.session_id);
      setWsUrl(data.ws_url);
      setSessionConfig({
        startedAt: null,
        durationMinutes: config.duration_minutes || 30,
        status: "planning",
      });
      setScreen("planning");
      setTurns([]);
      setResults(null);
      setLoading(false);

      // Poll for planning completion
      const poll = setInterval(async () => {
        const sessionRes = await fetch(`/api/ai/interview/${data.session_id}`);
        if (sessionRes.ok) {
          const sessionData = await sessionRes.json();
          if (sessionData.session.status === "active") {
            clearInterval(poll);
            setSessionConfig((prev) => ({
              ...prev,
              startedAt: sessionData.session.started_at,
              status: "active",
            }));
            setTurns(
              sessionData.turns.map((t: Record<string, unknown>) => ({
                id: t.id,
                sessionId: t.session_id,
                turnNumber: t.turn_number,
                role: t.role,
                text: t.text,
                audioDurationMs: t.audio_duration_ms,
                planTopicRef: t.plan_topic_ref,
                createdAt: t.created_at,
              })),
            );
          }
        }
      }, 1000);
    },
    [job.id],
  );

  const endInterview = useCallback(async () => {
    if (!sessionId) return;
    sendEnd();
    setWsUrl(null); // Stop WebSocket before ending — prevents reconnect loop
    await fetch(`/api/ai/interview/${sessionId}/end`, { method: "PATCH" });
    setScreen("results");

    // Poll for scoring completion
    const poll = setInterval(async () => {
      const res = await fetch(`/api/ai/interview/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.results) {
          clearInterval(poll);
          setResults(data.results);
          fetchSessions();
        }
      }
    }, 1500);
  }, [sessionId, sendEnd, fetchSessions]);

  const pauseInterview = useCallback(async () => {
    if (!sessionId) return;
    await fetch(`/api/ai/interview/${sessionId}/pause`, { method: "PATCH" });
    setSessionConfig((prev) => ({ ...prev, status: "paused" }));
  }, [sessionId]);

  const resumeInterview = useCallback(async () => {
    if (!sessionId) return;
    await fetch(`/api/ai/interview/${sessionId}/resume`, { method: "PATCH" });
    setSessionConfig((prev) => ({ ...prev, status: "active" }));
  }, [sessionId]);

  const handleTextSubmit = useCallback(
    (text: string) => {
      setIsProcessing(true);
      sendText(text);
    },
    [sendText],
  );

  const viewSession = useCallback(async (id: number) => {
    const res = await fetch(`/api/ai/interview/${id}`);
    if (!res.ok) return;
    const data = await res.json();
    setSessionId(id);
    setTurns(
      data.turns.map((t: Record<string, unknown>) => ({
        id: t.id,
        sessionId: t.session_id,
        turnNumber: t.turn_number,
        role: t.role,
        text: t.text,
        audioDurationMs: t.audio_duration_ms,
        planTopicRef: t.plan_topic_ref,
        createdAt: t.created_at,
      })),
    );
    setResults(data.results);
    setScreen(data.results ? "results" : "active");
  }, []);

  return {
    screen,
    turns,
    streamingText,
    isRecording,
    isProcessing,
    micPermission,
    wsStatus,
    sessionConfig,
    results,
    sessions,
    loading,
    isPlaying,
    startInterview,
    endInterview,
    pauseInterview,
    resumeInterview,
    handleTextSubmit,
    viewSession,
    setScreen,
  };
}
