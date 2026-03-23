"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Combobox } from "@/components/combobox";
import { StarRating } from "@/components/star-rating";
import {
  JOB_STATUSES,
  JOB_TYPES,
  WORK_MODES,
  SOURCES,
  STATUS_LABELS,
  TYPE_LABELS,
  MODE_LABELS,
  SOURCE_LABELS,
} from "@/lib/types";

interface JobFormProps {
  initialData?: any;
  onSubmit: (data: any) => void;
  onCancel: () => void;
}

export function JobForm({ initialData, onSubmit, onCancel }: JobFormProps) {
  const isEditing = !!initialData;

  const [title, setTitle] = useState<string>(initialData?.title ?? "");
  const [company, setCompany] = useState<string>(initialData?.company ?? "");
  const [status, setStatus] = useState<string>(
    initialData?.status ?? "saved"
  );
  const [location, setLocation] = useState<string>(
    initialData?.location ?? ""
  );
  const [url, setUrl] = useState<string>(initialData?.url ?? "");
  const [salaryMin, setSalaryMin] = useState<string>(
    initialData?.salaryMin != null ? String(initialData.salaryMin) : ""
  );
  const [salaryMax, setSalaryMax] = useState<string>(
    initialData?.salaryMax != null ? String(initialData.salaryMax) : ""
  );
  const [salaryCurrency, setSalaryCurrency] = useState<string>(
    initialData?.salaryCurrency ?? ""
  );
  const [jobType, setJobType] = useState<string>(initialData?.jobType ?? "");
  const [workMode, setWorkMode] = useState<string>(
    initialData?.workMode ?? ""
  );
  const [source, setSource] = useState<string>(initialData?.source ?? "");

  const handleSelectChange =
    (setter: (v: string) => void) =>
    (value: string | null) => {
      setter(value ?? "");
    };
  const [dateApplied, setDateApplied] = useState<string>(
    initialData?.dateApplied ?? ""
  );
  const [contactName, setContactName] = useState<string>(
    initialData?.contactName ?? ""
  );
  const [contactEmail, setContactEmail] = useState<string>(
    initialData?.contactEmail ?? ""
  );
  const [resumeVersion, setResumeVersion] = useState<string>(
    initialData?.resumeVersion ?? ""
  );
  const [priority, setPriority] = useState<number | null>(
    initialData?.priority ?? null
  );
  const [description, setDescription] = useState<string>(
    initialData?.description ?? ""
  );
  const [notes, setNotes] = useState<string>(initialData?.notes ?? "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const nullIfEmpty = (v: string) => (v.trim() === "" ? null : v.trim());
    const toNum = (v: string) => {
      const n = parseFloat(v);
      return isNaN(n) ? null : n;
    };

    onSubmit({
      title: title.trim(),
      company: company.trim(),
      status,
      location: nullIfEmpty(location),
      url: nullIfEmpty(url),
      salaryMin: toNum(salaryMin),
      salaryMax: toNum(salaryMax),
      salaryCurrency: nullIfEmpty(salaryCurrency),
      jobType: nullIfEmpty(jobType),
      workMode: nullIfEmpty(workMode),
      source: nullIfEmpty(source),
      dateApplied: nullIfEmpty(dateApplied),
      contactName: nullIfEmpty(contactName),
      contactEmail: nullIfEmpty(contactEmail),
      resumeVersion: nullIfEmpty(resumeVersion),
      priority,
      description: nullIfEmpty(description),
      notes: nullIfEmpty(notes),
    });
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <h2 className="text-lg font-semibold">
          {isEditing ? "Edit Job" : "Add Job"}
        </h2>
      </div>

      {/* Scrollable fields */}
      <ScrollArea className="flex-1">
        <form id="job-form" onSubmit={handleSubmit}>
          <div className="space-y-4 px-6 py-4">
            {/* 1. Job Title */}
            <div className="space-y-1.5">
              <Label htmlFor="title">
                Job Title <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Software Engineer"
                required
              />
            </div>

            {/* 2. Company */}
            <div className="space-y-1.5">
              <Label>
                Company <span className="text-destructive">*</span>
              </Label>
              <Combobox
                value={company}
                onChange={setCompany}
                placeholder="Select or type company..."
                field="company"
              />
            </div>

            {/* 3. Status */}
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={status} onValueChange={handleSelectChange(setStatus)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select status..." />
                </SelectTrigger>
                <SelectContent>
                  {JOB_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 4. Location */}
            <div className="space-y-1.5">
              <Label>Location</Label>
              <Combobox
                value={location}
                onChange={setLocation}
                placeholder="Select or type location..."
                field="location"
              />
            </div>

            {/* 5. Job URL */}
            <div className="space-y-1.5">
              <Label htmlFor="url">Job URL</Label>
              <Input
                id="url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://..."
              />
            </div>

            {/* 6. Salary range: Min, Max, Currency */}
            <div className="space-y-1.5">
              <Label>Salary Range</Label>
              <div className="grid grid-cols-3 gap-2">
                <Input
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  placeholder="Min"
                  type="number"
                  min={0}
                />
                <Input
                  value={salaryMax}
                  onChange={(e) => setSalaryMax(e.target.value)}
                  placeholder="Max"
                  type="number"
                  min={0}
                />
                <Input
                  value={salaryCurrency}
                  onChange={(e) => setSalaryCurrency(e.target.value)}
                  placeholder="Currency"
                  maxLength={10}
                />
              </div>
            </div>

            {/* 7. Job Type + Work Mode */}
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Job Type</Label>
                <Select value={jobType} onValueChange={handleSelectChange(setJobType)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select type..." />
                  </SelectTrigger>
                  <SelectContent>
                    {JOB_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {TYPE_LABELS[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Work Mode</Label>
                <Select value={workMode} onValueChange={handleSelectChange(setWorkMode)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select mode..." />
                  </SelectTrigger>
                  <SelectContent>
                    {WORK_MODES.map((m) => (
                      <SelectItem key={m} value={m}>
                        {MODE_LABELS[m]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 8. Source */}
            <div className="space-y-1.5">
              <Label>Source</Label>
              <Select value={source} onValueChange={handleSelectChange(setSource)}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select source..." />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {SOURCE_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 9. Date Applied */}
            <div className="space-y-1.5">
              <Label htmlFor="dateApplied">Date Applied</Label>
              <Input
                id="dateApplied"
                type="date"
                value={dateApplied}
                onChange={(e) => setDateApplied(e.target.value)}
              />
            </div>

            {/* 10. Contact Name + Contact Email */}
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label>Contact Name</Label>
                <Combobox
                  value={contactName}
                  onChange={setContactName}
                  placeholder="Contact name..."
                  field="contactName"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Contact Email</Label>
                <Combobox
                  value={contactEmail}
                  onChange={setContactEmail}
                  placeholder="Contact email..."
                  field="contactEmail"
                />
              </div>
            </div>

            {/* 11. Resume Version */}
            <div className="space-y-1.5">
              <Label>Resume Version</Label>
              <Combobox
                value={resumeVersion}
                onChange={setResumeVersion}
                placeholder="Select or type resume version..."
                field="resumeVersion"
              />
            </div>

            {/* 12. Priority */}
            <div className="space-y-1.5">
              <Label>Priority</Label>
              <StarRating value={priority} onChange={setPriority} />
            </div>

            {/* 13. Job Description */}
            <div className="space-y-1.5">
              <Label htmlFor="description">Job Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Paste the job description here..."
                rows={6}
              />
            </div>

            {/* 14. Notes */}
            <div className="space-y-1.5">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Any personal notes..."
                rows={3}
              />
            </div>
          </div>
        </form>
      </ScrollArea>

      {/* Footer */}
      <div className="flex justify-end gap-2 border-t px-6 py-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" form="job-form">
          {isEditing ? "Save Changes" : "Add Job"}
        </Button>
      </div>
    </div>
  );
}
