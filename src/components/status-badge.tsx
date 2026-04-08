import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const statusConfig: Record<JobStatus, { label: string; className: string }> = {
  saved: {
    label: "Saved",
    className: "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20",
  },
  applied: {
    label: "Applied",
    className: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/20",
  },
  phone_screen: {
    label: "Phone Screen",
    className: "bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/20",
  },
  interview: {
    label: "Interview",
    className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/20",
  },
  offer: {
    label: "Offer",
    className: "bg-violet-500/15 text-violet-700 dark:text-violet-300 border-violet-500/20",
  },
  accepted: {
    label: "Accepted",
    className: "bg-green-500/15 text-green-700 dark:text-green-300 border-green-500/20",
  },
  rejected: {
    label: "Rejected",
    className: "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/20",
  },
  withdrawn: {
    label: "Withdrawn",
    className: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/20",
  },
  ghosted: {
    label: "Ghosted",
    className: "bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20",
  },
};

export function StatusBadge({ status }: { status: JobStatus }) {
  const config = statusConfig[status];
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
