"use client";

import { useEffect, useState, useCallback } from "react";
import { ResumeCard } from "@/components/resume-card";
import { ResumeUpload } from "@/components/resume-upload";
import type { Resume } from "@/lib/types";

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);

  const fetchResumes = useCallback(async () => {
    try {
      const res = await fetch("/api/resumes");
      if (!res.ok) throw new Error("Failed to fetch resumes");
      setResumes(await res.json());
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

  async function handleDelete(id: number) {
    try {
      const res = await fetch(`/api/resumes/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete resume");
      await fetchResumes();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Resumes</h1>
        <ResumeUpload onUpload={fetchResumes} />
      </div>

      {resumes.length === 0 ? (
        <p className="text-muted-foreground">
          No resumes uploaded yet. Upload your first resume to get started.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {resumes.map((resume) => (
            <ResumeCard
              key={resume.id}
              resume={resume}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
