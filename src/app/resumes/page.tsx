"use client";

import { useEffect, useState, useCallback } from "react";
import { ResumeCard } from "@/components/resume-card";
import { ResumeUpload } from "@/components/resume-upload";
import { EmbeddingStatusBanner } from "@/components/embedding-status-banner";
import { useEmbeddingStatus } from "@/hooks/use-embedding-status";
import type { Resume } from "@/lib/types";

export default function ResumesPage() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const { status: embeddingStatus, refresh: refreshEmbedding } = useEmbeddingStatus();

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
      await refreshEmbedding();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleReindex(resumeIds?: number[]) {
    try {
      const res = await fetch("/api/ai/embedding/reindex", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ resume_ids: resumeIds ?? null }),
      });
      if (!res.ok) {
        const body = await res.json();
        console.error("Reindex rejected:", body);
        return;
      }
      await refreshEmbedding();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="space-y-6 px-8 py-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Resumes</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your resumes and track AI embeddings
          </p>
        </div>
        <ResumeUpload
          onUpload={async () => {
            await fetchResumes();
            await refreshEmbedding();
          }}
        />
      </div>

      {embeddingStatus && (
        <EmbeddingStatusBanner status={embeddingStatus} onReindex={handleReindex} />
      )}

      {resumes.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 py-16">
          <p className="text-muted-foreground">
            No resumes uploaded yet. Upload your first resume to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {resumes.map((resume) => {
            const statusRow = embeddingStatus?.resumes.find((r) => r.id === resume.id);
            return (
              <ResumeCard
                key={resume.id}
                resume={resume}
                onDelete={handleDelete}
                embeddingStatus={statusRow ?? null}
                activeSignature={embeddingStatus?.active_signature ?? null}
                configuredSignature={embeddingStatus?.configured_signature ?? ""}
                isIndexing={
                  embeddingStatus?.active_job?.current_resume_id === resume.id
                }
                onReindex={() => handleReindex([resume.id])}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
