"use client";

import { useEffect, useState, useCallback } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JobTable } from "@/components/job-table";
import { JobPanel } from "@/components/job-panel";
import { JobForm } from "@/components/job-form";
import { AiWorkspace } from "@/components/ai-workspace";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import type { Job } from "@/lib/types";

export default function ApplicationsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [addingNew, setAddingNew] = useState(false);
  const [aiJob, setAiJob] = useState<Job | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch("/api/jobs");
      if (!res.ok) throw new Error("Failed to fetch jobs");
      const data = await res.json();
      setJobs(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  async function handleRowClick(id: number) {
    try {
      const res = await fetch(`/api/jobs/${id}`);
      if (!res.ok) throw new Error("Failed to fetch job");
      const job: Job = await res.json();
      setSelectedJob(job);
      setPanelOpen(true);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleCreate(data: any) {
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to create job");
      setAddingNew(false);
      await fetchJobs();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleUpdate(id: number, data: any) {
    try {
      const res = await fetch(`/api/jobs/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to update job");
      const updated: Job = await res.json();
      setSelectedJob(updated);
      await fetchJobs();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleDelete(id: number) {
    try {
      const res = await fetch(`/api/jobs/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete job");
      setPanelOpen(false);
      setSelectedJob(null);
      await fetchJobs();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <>
      {aiJob ? (
        <AiWorkspace
          job={aiJob}
          onClose={() => setAiJob(null)}
        />
      ) : (
        <div className="space-y-6 px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Applications</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Track and manage your job applications
              </p>
            </div>
            <Button onClick={() => setAddingNew(true)}>
              <Plus className="mr-1.5 size-4" />
              Add Job
            </Button>
          </div>

          <JobTable jobs={jobs} onRowClick={handleRowClick} />

          <JobPanel
            job={selectedJob}
            open={panelOpen}
            onClose={() => {
              setPanelOpen(false);
              setSelectedJob(null);
            }}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onOpenAi={(job) => setAiJob(job)}
          />

          <Sheet open={addingNew} onOpenChange={(open) => setAddingNew(open)}>
            <SheetContent side="right" showCloseButton={false} className="w-full sm:max-w-lg flex flex-col p-0 gap-0">
              <JobForm
                onSubmit={handleCreate}
                onCancel={() => setAddingNew(false)}
              />
            </SheetContent>
          </Sheet>
        </div>
      )}
    </>
  );
}
