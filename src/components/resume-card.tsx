"use client";

import { FileText, Trash2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmbeddingStatusBadge } from "@/components/embedding-status-badge";
import type { EmbeddingResumeStatus, Resume } from "@/lib/types";

interface ResumeCardProps {
  resume: Resume;
  onDelete: (id: number) => void;
  embeddingStatus?: EmbeddingResumeStatus | null;
  activeSignature?: string | null;
  configuredSignature?: string;
  isIndexing?: boolean;
  onReindex?: () => void;
}

export function ResumeCard({
  resume,
  onDelete,
  embeddingStatus,
  activeSignature,
  configuredSignature,
  isIndexing,
  onReindex,
}: ResumeCardProps) {
  return (
    <Card className="flex flex-col gap-4 p-5 transition-[shadow,border-color] duration-200 hover:shadow-lg hover:shadow-indigo-500/5 hover:border-white/10">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10">
            <FileText className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h3 className="font-semibold">{resume.name}</h3>
            {resume.version && (
              <p className="text-sm text-muted-foreground">{resume.version}</p>
            )}
          </div>
        </div>
        <Badge variant="secondary" className="text-xs">
          {resume.fileType.toUpperCase()}
        </Badge>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{new Date(resume.createdAt).toLocaleDateString()}</span>
        <span className={resume.extractedText ? "text-emerald-400" : ""}>
          {resume.extractedText ? "Text extracted" : "Processing..."}
        </span>
      </div>

      {embeddingStatus && (
        <div className="flex items-center gap-2">
          <EmbeddingStatusBadge
            resumeStatus={embeddingStatus}
            activeSignature={activeSignature ?? null}
            configuredSignature={configuredSignature ?? ""}
            isIndexing={isIndexing ?? false}
          />
          {onReindex && embeddingStatus.last_index_status !== "ok" && (
            <button
              type="button"
              onClick={onReindex}
              className="text-xs font-medium text-indigo-400 hover:underline cursor-pointer"
            >
              Reindex
            </button>
          )}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <Button
          variant="outline"
          size="sm"
          className="cursor-pointer"
          onClick={() => window.open(`/${resume.filePath}`, "_blank")}
        >
          <Download className="mr-1.5 h-3.5 w-3.5" />
          Download
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive cursor-pointer"
          onClick={() => onDelete(resume.id)}
        >
          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
          Delete
        </Button>
      </div>
    </Card>
  );
}
