"use client";

import { useState, useEffect } from "react";
import { useInterviewSession } from "@/hooks/use-interview-session";
import { InterviewSetup } from "@/components/interview-setup";
import { InterviewActive } from "@/components/interview-active";
import { InterviewResults } from "@/components/interview-results";
import { InterviewHistorySidebar } from "@/components/interview-history-sidebar";
import type { Job, Resume } from "@/lib/types";

interface MockInterviewTabProps {
  job: Job;
}

export function MockInterviewTab({ job }: MockInterviewTabProps) {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const session = useInterviewSession(job);

  useEffect(() => {
    fetch("/api/resumes")
      .then((r) => r.json())
      .then(setResumes)
      .catch(() => {});
  }, []);

  const parsedResults = session.results
    ? {
        overallScore: (session.results as Record<string, unknown>).overall_score as number,
        dimensionScores: JSON.parse(
          (session.results as Record<string, unknown>).dimension_scores_json as string,
        ),
        strengths: JSON.parse(
          (session.results as Record<string, unknown>).strengths_json as string,
        ),
        improvements: JSON.parse(
          (session.results as Record<string, unknown>).improvements_json as string,
        ),
        modelAnswers: JSON.parse(
          (session.results as Record<string, unknown>).model_answers_json as string,
        ),
        summary: (session.results as Record<string, unknown>).summary as string,
      }
    : null;

  return (
    <div className="flex gap-4">
      <InterviewHistorySidebar
        sessions={session.sessions}
        selectedId={null}
        onSelect={session.viewSession}
      />
      <div className="flex-1">
        {session.screen === "setup" && (
          <InterviewSetup
            job={job}
            resumes={resumes}
            onStart={session.startInterview}
            loading={session.loading}
          />
        )}
        {session.screen === "planning" && (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm text-muted-foreground animate-pulse">
              Preparing your interview...
            </p>
          </div>
        )}
        {session.screen === "active" && (
          <InterviewActive
            turns={session.turns}
            streamingText={session.streamingText}
            startedAt={session.sessionConfig.startedAt}
            durationMinutes={session.sessionConfig.durationMinutes}
            isPaused={session.sessionConfig.status === "paused"}
            isRecording={session.isRecording}
            isProcessing={session.isProcessing}
            micPermission={session.micPermission}
            connectionStatus={session.wsStatus}
            onPause={session.pauseInterview}
            onResume={session.resumeInterview}
            onEnd={session.endInterview}
            onTextSubmit={session.handleTextSubmit}
          />
        )}
        {session.screen === "results" && parsedResults && (
          <InterviewResults
            {...parsedResults}
            turns={session.turns}
            onNewInterview={() => session.setScreen("setup")}
          />
        )}
        {session.screen === "results" && !parsedResults && (
          <div className="flex items-center justify-center py-20">
            <p className="text-sm text-muted-foreground animate-pulse">
              Scoring your interview...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
