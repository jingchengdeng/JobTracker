"use client";

import { useState } from "react";
import {
  ExternalLink,
  Pencil,
  Trash2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { StatusBadge } from "@/components/status-badge";
import { StarRating } from "@/components/star-rating";
import { JobForm } from "@/components/job-form";
import { type Job, TYPE_LABELS, MODE_LABELS, SOURCE_LABELS } from "@/lib/types";

interface JobPanelProps {
  job: Job | null;
  open: boolean;
  onClose: () => void;
  onUpdate: (id: number, data: any) => void;
  onDelete: (id: number) => void;
  onOpenAi?: (job: Job) => void;
}

function formatSalary(
  min: number | null,
  max: number | null,
  currency: string | null
): string | null {
  if (min == null && max == null) return null;
  const locale = "en-US";
  const currencyCode = currency && currency.length === 3 ? currency : "USD";
  const fmt = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
    maximumFractionDigits: 0,
  });
  if (min != null && max != null) {
    return `${fmt.format(min)} – ${fmt.format(max)}`;
  }
  if (min != null) return `From ${fmt.format(min)}`;
  if (max != null) return `Up to ${fmt.format(max!)}`;
  return null;
}

function MetaItem({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  if (!value && value !== 0) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function JobPanel({
  job,
  open,
  onClose,
  onUpdate,
  onDelete,
  onOpenAi,
}: JobPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);

  // Reset edit mode when job changes or panel closes
  function handleOpenChange(o: boolean) {
    if (!o) {
      setIsEditing(false);
      setDeleteDialogOpen(false);
      onClose();
    }
  }

  function handleFormSubmit(data: any) {
    if (!job) return;
    onUpdate(job.id, data);
    setIsEditing(false);
  }

  function handleDeleteConfirm() {
    if (!job) return;
    onDelete(job.id);
    setDeleteDialogOpen(false);
    onClose();
  }

  if (!job) return null;

  const salary = formatSalary(job.salaryMin, job.salaryMax, job.salaryCurrency);

  return (
    <>
      <Sheet open={open} onOpenChange={handleOpenChange}>
        <SheetContent
          side="right"
          showCloseButton={!isEditing}
          className="w-full sm:max-w-lg flex flex-col p-0 gap-0"
        >
          {isEditing ? (
            <JobForm
              initialData={job}
              onSubmit={handleFormSubmit}
              onCancel={() => setIsEditing(false)}
            />
          ) : (
            <>
              {/* Header */}
              <SheetHeader className="border-b px-5 py-4 pr-14">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <SheetTitle className="text-base font-semibold leading-tight">
                      {job.title}
                    </SheetTitle>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      {job.company}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {onOpenAi && (
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => onOpenAi(job)}
                      >
                        AI Assistant
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setIsEditing(true)}
                      aria-label="Edit job"
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setDeleteDialogOpen(true)}
                      aria-label="Delete job"
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>

                {/* Tags row */}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusBadge status={job.status} />
                  {job.workMode && (
                    <Badge variant="outline">
                      {MODE_LABELS[job.workMode]}
                    </Badge>
                  )}
                  {job.jobType && (
                    <Badge variant="outline">
                      {TYPE_LABELS[job.jobType]}
                    </Badge>
                  )}
                </div>
              </SheetHeader>

              {/* Scrollable body */}
              <ScrollArea className="min-h-0 flex-1">
                <div className="space-y-5 px-5 py-4">
                  {/* Metadata grid */}
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    <MetaItem label="Location" value={job.location} />
                    <MetaItem label="Salary" value={salary} />
                    <MetaItem
                      label="Source"
                      value={
                        job.source ? SOURCE_LABELS[job.source] : null
                      }
                    />
                    <MetaItem label="Date Applied" value={job.dateApplied} />
                    <MetaItem label="Contact Name" value={job.contactName} />
                    <MetaItem label="Contact Email" value={job.contactEmail} />
                    <MetaItem label="Resume Version" value={job.resumeVersion} />
                    {job.priority != null && (
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs text-muted-foreground">
                          Priority
                        </span>
                        <StarRating value={job.priority} readonly />
                      </div>
                    )}
                  </div>

                  {/* Job URL */}
                  {job.url && (
                    <>
                      <Separator />
                      <div>
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-sm text-primary underline-offset-4 hover:underline"
                        >
                          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                          View Job Posting
                        </a>
                      </div>
                    </>
                  )}

                  {/* Notes */}
                  {job.notes && (
                    <>
                      <Separator />
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Notes
                        </p>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed">
                          {job.notes}
                        </p>
                      </div>
                    </>
                  )}

                  {/* Job Description */}
                  {job.description && (
                    <>
                      <Separator />
                      <div className="space-y-1.5">
                        <button
                          type="button"
                          onClick={() => setDescExpanded((v) => !v)}
                          className="flex w-full items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground"
                        >
                          <span>Job Description</span>
                          {descExpanded ? (
                            <ChevronUp className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronDown className="h-3.5 w-3.5" />
                          )}
                        </button>
                        {descExpanded && (
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">
                            {job.description}
                          </p>
                        )}
                      </div>
                    </>
                  )}

                  {/* Interview Dates */}
                  {job.interviewDates && job.interviewDates.length > 0 && (
                    <>
                      <Separator />
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                          Interview Dates
                        </p>
                        <ul className="space-y-1">
                          {job.interviewDates.map((date, i) => (
                            <li key={i} className="text-sm">
                              {date}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </>
                  )}
                </div>
              </ScrollArea>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Delete this application?</DialogTitle>
            <DialogDescription>
              This will permanently remove{" "}
              <strong>
                {job.title} at {job.company}
              </strong>{" "}
              from your tracker. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>
              Cancel
            </DialogClose>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
