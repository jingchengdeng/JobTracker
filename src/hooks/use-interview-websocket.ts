"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

interface WSMessage {
  type: string;
  [key: string]: unknown;
}

interface UseInterviewWebSocketReturn {
  status: ConnectionStatus;
  sendAudio: (blob: Blob) => void;
  sendText: (content: string) => void;
  sendPing: () => void;
  sendEnd: () => void;
  lastMessage: WSMessage | null;
  lastAudioChunk: ArrayBuffer | null;
}

export function useInterviewWebSocket(
  wsUrl: string | null,
  onMessage?: (msg: WSMessage) => void,
  onAudioChunk?: (chunk: ArrayBuffer) => void,
): UseInterviewWebSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [lastAudioChunk, setLastAudioChunk] = useState<ArrayBuffer | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const maxRetries = 5;
  const receivingAudioRef = useRef(false);

  // Store callbacks in refs so they never trigger reconnects
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onAudioChunkRef = useRef(onAudioChunk);
  onAudioChunkRef.current = onAudioChunk;

  const connect = useCallback(() => {
    if (!wsUrl) return;

    setStatus(retriesRef.current > 0 ? "reconnecting" : "connecting");
    const ws = new WebSocket(wsUrl);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      setStatus("connected");
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        setLastAudioChunk(event.data);
        onAudioChunkRef.current?.(event.data);
        return;
      }

      try {
        const msg = JSON.parse(event.data) as WSMessage;
        if (msg.type === "audio_start") {
          receivingAudioRef.current = true;
        } else if (msg.type === "audio_end") {
          receivingAudioRef.current = false;
        }
        setLastMessage(msg);
        onMessageRef.current?.(msg);
      } catch {
        // Ignore non-JSON text
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (retriesRef.current < maxRetries) {
        setStatus("reconnecting");
        const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 16000);
        retriesRef.current += 1;
        setTimeout(connect, delay);
      } else {
        setStatus("disconnected");
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [wsUrl]);

  useEffect(() => {
    connect();
    return () => {
      retriesRef.current = maxRetries; // Prevent reconnect on unmount
      wsRef.current?.close();
    };
  }, [connect]);

  const sendAudio = useCallback(async (blob: Blob) => {
    const buffer = await blob.arrayBuffer();
    wsRef.current?.send(buffer);
  }, []);

  const sendText = useCallback((content: string) => {
    wsRef.current?.send(JSON.stringify({ type: "text", content }));
  }, []);

  const sendPing = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "ping" }));
  }, []);

  const sendEnd = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: "end_interview" }));
  }, []);

  return { status, sendAudio, sendText, sendPing, sendEnd, lastMessage, lastAudioChunk };
}
