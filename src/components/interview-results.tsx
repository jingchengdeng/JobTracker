"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface DimensionScore {
  name: string;
  score: number;
  feedback: string;
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
  onNewInterview: () => void;
  onViewTranscript: () => void;
}

export function InterviewResults({
  overallScore, dimensionScores, strengths, improvements,
  modelAnswers, summary, onNewInterview, onViewTranscript,
}: InterviewResultsProps) {
  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h3 className="mb-3 font-medium">Interview Results</h3>

        <div className="mb-4 flex gap-3">
          <div className="flex-1 rounded border p-3 text-center">
            <p className="text-2xl font-bold">{overallScore}</p>
            <p className="text-xs text-muted-foreground">Overall Score</p>
          </div>
          {dimensionScores.map((d) => (
            <div key={d.name} className="flex-1 rounded border p-3 text-center">
              <p className="text-2xl font-bold">{d.score}</p>
              <p className="text-xs text-muted-foreground">{d.name}</p>
            </div>
          ))}
        </div>

        <p className="mb-4 text-sm text-muted-foreground">{summary}</p>

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

        <div className="mt-4 flex gap-2">
          <Button variant="outline" onClick={onViewTranscript}>View Transcript</Button>
          <Button onClick={onNewInterview}>New Interview</Button>
        </div>
      </Card>
    </div>
  );
}
