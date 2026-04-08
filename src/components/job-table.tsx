"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown, Search } from "lucide-react";
import { Job, JobStatus, JOB_STATUSES, STATUS_LABELS } from "@/lib/types";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { StarRating } from "@/components/star-rating";
import { Card } from "@/components/ui/card";

interface JobTableProps {
  jobs: Job[];
  onRowClick: (id: number) => void;
}

type SortKey = "title" | "company" | "status" | "priority" | "dateApplied";
type SortDir = "asc" | "desc";

function formatSalary(min: number | null, max: number | null): string {
  if (!min && !max) return "\u2014";
  const fmt = (n: number) => {
    if (n >= 1000) return `$${Math.round(n / 1000)}k`;
    return `$${n}`;
  };
  if (min && max) return `${fmt(min)}-${fmt(max)}`;
  if (min) return `${fmt(min)}+`;
  if (max) return `Up to ${fmt(max)}`;
  return "\u2014";
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function JobTable({ jobs, onRowClick }: JobTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | JobStatus>("all");
  const [sortKey, setSortKey] = useState<SortKey>("dateApplied");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const filtered = useMemo(() => {
    let result = jobs;

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (j) =>
          j.title.toLowerCase().includes(q) ||
          j.company.toLowerCase().includes(q)
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((j) => j.status === statusFilter);
    }

    result = [...result].sort((a, b) => {
      let aVal: string | number | null = null;
      let bVal: string | number | null = null;

      if (sortKey === "title") {
        aVal = a.title.toLowerCase();
        bVal = b.title.toLowerCase();
      } else if (sortKey === "company") {
        aVal = a.company.toLowerCase();
        bVal = b.company.toLowerCase();
      } else if (sortKey === "status") {
        aVal = a.status;
        bVal = b.status;
      } else if (sortKey === "priority") {
        aVal = a.priority ?? -1;
        bVal = b.priority ?? -1;
      } else if (sortKey === "dateApplied") {
        aVal = a.dateApplied ?? "";
        bVal = b.dateApplied ?? "";
      }

      if (aVal === null || aVal === bVal) return 0;
      if (aVal < (bVal ?? "")) return sortDir === "asc" ? -1 : 1;
      return sortDir === "asc" ? 1 : -1;
    });

    return result;
  }, [jobs, search, statusFilter, sortKey, sortDir]);

  const SortHeader = ({
    label,
    colKey,
  }: {
    label: string;
    colKey: SortKey;
  }) => (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2.5 h-auto gap-1 font-medium text-muted-foreground"
      onClick={() => handleSort(colKey)}
    >
      {label}
      <ArrowUpDown className="size-3 opacity-50" />
    </Button>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by title or company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(val) =>
            setStatusFilter(val as "all" | JobStatus)
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {JOB_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>
                <SortHeader label="Title" colKey="title" />
              </TableHead>
              <TableHead>
                <SortHeader label="Company" colKey="company" />
              </TableHead>
              <TableHead>
                <SortHeader label="Status" colKey="status" />
              </TableHead>
              <TableHead>Salary</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>
                <SortHeader label="Priority" colKey="priority" />
              </TableHead>
              <TableHead>
                <SortHeader label="Date Applied" colKey="dateApplied" />
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="h-32 text-center text-muted-foreground"
                >
                  No jobs found. Add your first application!
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((job) => (
                <TableRow
                  key={job.id}
                  className="cursor-pointer transition-colors"
                  onClick={() => onRowClick(job.id)}
                >
                  <TableCell className="font-medium">{job.title}</TableCell>
                  <TableCell className="text-muted-foreground">{job.company}</TableCell>
                  <TableCell>
                    <StatusBadge status={job.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatSalary(job.salaryMin, job.salaryMax)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {job.location ?? "\u2014"}
                  </TableCell>
                  <TableCell>
                    <StarRating value={job.priority} readonly />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(job.dateApplied)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
