"use client";

import { FileText, Trash2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Resume } from "@/lib/types";

interface ResumeCardProps {
  resume: Resume;
  onDelete: (id: number) => void;
}

export function ResumeCard({ resume, onDelete }: ResumeCardProps) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <FileText className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="font-medium">{resume.name}</h3>
            {resume.version && (
              <p className="text-sm text-muted-foreground">{resume.version}</p>
            )}
          </div>
        </div>
        <Badge variant="secondary">{resume.fileType.toUpperCase()}</Badge>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>{new Date(resume.createdAt).toLocaleDateString()}</span>
        <span>
          {resume.extractedText ? "Text extracted" : "Processing..."}
        </span>
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => window.open(`/${resume.filePath}`, "_blank")}
        >
          <Download className="mr-1.5 h-3.5 w-3.5" />
          Download
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive hover:text-destructive"
          onClick={() => onDelete(resume.id)}
        >
          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
          Delete
        </Button>
      </div>
    </Card>
  );
}
