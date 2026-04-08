"use client";

import { useState } from "react";
import { ArrowLeft, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { ResumeTailorTab } from "@/components/resume-tailor-tab";
import { LinkedinTab } from "@/components/linkedin-tab";
import { MockInterviewTab } from "@/components/mock-interview-tab";
import type { Job } from "@/lib/types";

const tabs = [
  { id: "resume", label: "Resume Tailor" },
  { id: "linkedin", label: "LinkedIn Search" },
  { id: "interview", label: "Mock Interview" },
] as const;

type TabId = (typeof tabs)[number]["id"];

interface AiWorkspaceProps {
  job: Job;
  onClose: () => void;
}

export function AiWorkspace({ job, onClose }: AiWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabId>("resume");

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4 border-b border-white/[0.06] px-6 py-3 bg-white/[0.02] backdrop-blur-xl">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <div className="h-5 w-px bg-white/[0.08]" />

        <div className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles className="h-4 w-4 text-indigo-400" />
          <span>AI Workspace</span>
          <span className="text-muted-foreground">for {job.title} at {job.company}</span>
        </div>

        <div className="ml-auto flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer",
                activeTab === tab.id
                  ? "bg-indigo-500/15 text-indigo-300 dark:text-indigo-300 text-indigo-700"
                  : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "resume" && <ResumeTailorTab job={job} />}
        {activeTab === "linkedin" && <LinkedinTab job={job} />}
        {activeTab === "interview" && <MockInterviewTab job={job} />}
      </div>
    </div>
  );
}
