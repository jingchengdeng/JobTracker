"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
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
      <div className="flex items-center gap-4 border-b px-4 py-3">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Applications
        </button>

        <div className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "pb-0.5 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "border-b-2 border-primary text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "resume" && <ResumeTailorTab job={job} />}
        {activeTab === "linkedin" && <LinkedinTab job={job} />}
        {activeTab === "interview" && <MockInterviewTab job={job} />}
      </div>
    </div>
  );
}
