"use client";

import { useEffect, useState } from "react";
import { registerEmbeddingMismatchToast } from "@/lib/fetch-with-embedding-check";

export function EmbeddingToastBridge() {
  const [msg, setMsg] = useState<{ text: string; href?: string } | null>(null);

  useEffect(() => {
    registerEmbeddingMismatchToast((text, href) => {
      setMsg({ text, href });
      const timer = setTimeout(() => setMsg(null), 6000);
      return () => clearTimeout(timer);
    });
  }, []);

  if (!msg) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-amber-900 shadow-lg">
      <p className="text-sm">{msg.text}</p>
      {msg.href && (
        <a href={msg.href} className="text-sm font-medium underline">
          View resumes
        </a>
      )}
    </div>
  );
}
