"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { InterviewTranscript } from "@/components/interview-transcript";
import type { InterviewTurn } from "@/lib/types";

interface DimensionScore {
  name: string;
  score: number;
  feedback: string;
  evidence: string;
}

interface ModelAnswer {
  question: string;
  user_answer_summary: string;
  model_answer: string;
  gap: string;
}

interface InterviewResultsProps {
  overallScore: number;
  dimensionScores: DimensionScore[];
  strengths: string[];
  improvements: string[];
  modelAnswers: ModelAnswer[];
  summary: string;
  turns: InterviewTurn[];
  onNewInterview: () => void;
}

export function InterviewResults({
  overallScore, dimensionScores, strengths, improvements,
  modelAnswers, summary, turns, onNewInterview,
}: InterviewResultsProps) {
  const [view, setView] = useState<"scores" | "transcript">("scores");

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button
          variant={view === "scores" ? "default" : "outline"}
          size="sm"
          onClick={() => setView("scores")}
        >
          Scores
        </Button>
        <Button
          variant={view === "transcript" ? "default" : "outline"}
          size="sm"
          onClick={() => setView("transcript")}
        >
          Transcript
        </Button>
        <Button variant="outline" size="sm" onClick={onNewInterview}>
          New Interview
        </Button>
      </div>

      {view === "transcript" ? (
        <Card className="p-4">
          <InterviewTranscript turns={turns} streamingText={null} />
        </Card>
      ) : (
        <Card className="p-4">
          <h3 className="mb-3 font-medium">Interview Results</h3>

          <div className="mb-4 flex gap-3">
            <div className="flex-1 rounded border p-3 text-center">
              <p className="text-2xl font-bold">{overallScore}/50</p>
              <p className="text-xs text-muted-foreground">Overall Score</p>
            </div>
            {dimensionScores.map((d, i) => (
              <div key={i} className="flex-1 rounded border p-3 text-center">
                <p className="text-2xl font-bold">{d.score}/10</p>
                <p className="text-xs text-muted-foreground">{d.name}</p>
              </div>
            ))}
          </div>

          <p className="mb-4 text-sm text-muted-foreground">{summary}</p>

          <div className="mb-4 space-y-2">
            {dimensionScores.map((d, i) => (
              <div key={i} className="rounded border p-3">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-medium">{d.name}</p>
                  <p className="text-sm font-bold">{d.score}/10</p>
                </div>
                <p className="text-sm text-muted-foreground">{d.feedback}</p>
                {d.evidence && (
                  <p className="mt-1 text-xs italic text-muted-foreground border-l-2 pl-2">
                    {d.evidence}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="mb-4 grid grid-cols-2 gap-4">
            <div>
              <p className="mb-1 text-sm font-medium text-green-600">Strengths</p>
              <ul className="space-y-1">
                {strengths.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-sm font-medium text-amber-600">Areas to Improve</p>
              <ul className="space-y-1">
                {improvements.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {modelAnswers.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-medium">Model Answers</p>
              <div className="space-y-2">
                {modelAnswers.map((ma, i) => (
                  <div key={i} className="rounded border p-3">
                    <p className="text-xs font-medium">Q: {ma.question}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Your answer: {ma.user_answer_summary}</p>
                    <p className="mt-1 text-xs">{ma.model_answer}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
