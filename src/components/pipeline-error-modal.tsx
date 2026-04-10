"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";

export type PipelineErrorModalProps = {
  open: boolean;
  onClose: () => void;
  nodeName: string;
  graph: string;
  attempt: number;
  maxAttempts: number;
  durationMs: number | null;
  startedAt: string | null;
  error: string;
  traceback: string | null;
};

export function PipelineErrorModal(props: PipelineErrorModalProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    const blob = [
      `Node: ${props.graph}.${props.nodeName}`,
      `Attempt: ${props.attempt}/${props.maxAttempts}`,
      `Error: ${props.error}`,
      "",
      props.traceback || "",
    ].join("\n");
    await navigator.clipboard.writeText(blob);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <Dialog open={props.open} onOpenChange={(o) => { if (!o) props.onClose(); }}>
      <DialogContent className="bg-[#1e1b4b]/90 border-white/[0.08] backdrop-blur-2xl rounded-xl max-w-2xl">
        <DialogHeader>
          <div className="text-[10.5px] font-mono uppercase tracking-wider text-red-300">
            Failed · Attempt {props.attempt} of {props.maxAttempts}
          </div>
          <DialogTitle className="text-lg font-semibold">
            {props.graph}.{props.nodeName}
          </DialogTitle>
          <div className="text-xs text-muted-foreground">
            {props.startedAt ? new Date(props.startedAt).toLocaleString() : ""}
            {props.durationMs != null && ` · ${props.durationMs}ms`}
          </div>
        </DialogHeader>

        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {props.error}
        </div>

        {props.traceback && (
          <pre className="max-h-64 overflow-auto rounded-lg border border-white/[0.06] bg-black/40 p-3 font-mono text-xs leading-relaxed text-red-200">
            {props.traceback}
          </pre>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={copy}>
            <Copy className="mr-1 h-3.5 w-3.5" />
            {copied ? "Copied" : "Copy error"}
          </Button>
          <Button size="sm" onClick={props.onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
