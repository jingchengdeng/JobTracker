"use client";

import { useCallback, useRef, useState } from "react";

export function useAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<ArrayBuffer[]>([]);
  const playingRef = useRef(false);

  const getContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }
    return audioContextRef.current;
  }, []);

  const playQueue = useCallback(async () => {
    if (playingRef.current) return;
    playingRef.current = true;
    setIsPlaying(true);

    const ctx = getContext();

    while (queueRef.current.length > 0) {
      const buffer = queueRef.current.shift()!;
      try {
        const audioBuffer = await ctx.decodeAudioData(buffer.slice(0));
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        source.start();
        await new Promise<void>((resolve) => { source.onended = () => resolve(); });
      } catch {
        // Skip undecodable chunks
      }
    }

    playingRef.current = false;
    setIsPlaying(false);
  }, [getContext]);

  const queueChunk = useCallback((data: ArrayBuffer) => {
    queueRef.current.push(data);
    playQueue();
  }, [playQueue]);

  const clearQueue = useCallback(() => {
    queueRef.current = [];
  }, []);

  return { isPlaying, queueChunk, clearQueue };
}
