"use client";

import { useState, useRef } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";

interface ResumeUploadProps {
  onUpload: () => void;
}

export function ResumeUpload({ onUpload }: ResumeUploadProps) {
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !name) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", name);
    if (version) formData.append("version", version);

    try {
      const res = await fetch("/api/resumes", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      setOpen(false);
      setName("");
      setVersion("");
      setFile(null);
      onUpload();
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <Upload className="mr-1.5 size-4" />
        Upload Resume
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Resume</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="resume-name">Name</Label>
            <Input
              id="resume-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Backend Engineer Resume"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="resume-version">Version (optional)</Label>
            <Input
              id="resume-version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g. v3"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="resume-file">File (PDF or DOCX)</Label>
            <Input
              id="resume-file"
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </div>
          <div className="flex justify-end gap-2">
            <DialogClose render={<Button type="button" variant="outline" />}>
              Cancel
            </DialogClose>
            <Button type="submit" disabled={uploading || !file || !name}>
              {uploading ? "Uploading..." : "Upload"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
