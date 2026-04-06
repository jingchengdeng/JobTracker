"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Job, Resume } from "@/lib/types";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

interface InterviewSetupProps {
  job: Job;
  resumes: Resume[];
  onStart: (config: {
    interview_type: string;
    difficulty: string;
    duration_minutes: number;
    focus_area: string | null;
    resume_id: number | null;
    voice: string;
  }) => void;
  loading: boolean;
}

const VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];

export function InterviewSetup({ job, resumes, onStart, loading }: InterviewSetupProps) {
  const [type, setType] = useState("technical");
  const [difficulty, setDifficulty] = useState("medium");
  const [duration, setDuration] = useState("30");
  const [focusArea, setFocusArea] = useState("");
  const [resumeId, setResumeId] = useState<string>(resumes[0]?.id?.toString() ?? "");
  const [voice, setVoice] = useState("nova");

  return (
    <Card className="p-4">
      <h3 className="mb-3 font-medium">Interview Setup</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-sm text-muted-foreground">Type</label>
          <Select value={type} onValueChange={(v) => v && setType(v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="behavioral">Behavioral</SelectItem>
              <SelectItem value="technical">Technical</SelectItem>
              <SelectItem value="system_design">System Design</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">Difficulty</label>
          <Select value={difficulty} onValueChange={(v) => v && setDifficulty(v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="easy">Easy</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="hard">Hard</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">Duration</label>
          <Select value={duration} onValueChange={(v) => v && setDuration(v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="15">15 minutes</SelectItem>
              <SelectItem value="30">30 minutes</SelectItem>
              <SelectItem value="45">45 minutes</SelectItem>
              <SelectItem value="60">60 minutes</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-sm text-muted-foreground">Focus Area</label>
          <input
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            placeholder="e.g. System Design"
            value={focusArea}
            onChange={(e) => setFocusArea(e.target.value)}
          />
        </div>
        {resumes.length > 0 && (
          <div className="col-span-2">
            <label className="text-sm text-muted-foreground">Resume</label>
            <Select value={resumeId} onValueChange={(v) => v && setResumeId(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {resumes.map((r) => (
                  <SelectItem key={r.id} value={r.id.toString()}>{r.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <div className="col-span-2">
          <label className="text-sm text-muted-foreground">Voice</label>
          <div className="flex flex-wrap gap-2 mt-1">
            {VOICES.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setVoice(v)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  voice === v ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>
      <Button
        className="mt-3"
        onClick={() => onStart({
          interview_type: type,
          difficulty,
          duration_minutes: parseInt(duration),
          focus_area: focusArea || null,
          resume_id: resumeId ? parseInt(resumeId) : null,
          voice,
        })}
        disabled={loading}
      >
        {loading ? "Starting..." : "Start Interview"}
      </Button>
      <p className="mt-1 text-xs text-muted-foreground">
        Hold Space to talk. Text fallback always available.
      </p>
    </Card>
  );
}
