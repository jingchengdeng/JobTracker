import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const statusConfig: Record<JobStatus, { label: string; className: string }> = {
  saved: {
    label: "Saved",
    className: "bg-zinc-500/15 text-zinc-400 border-zinc-500/20",
  },
  applied: {
    label: "Applied",
    className: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  },
  phone_screen: {
    label: "Phone Screen",
    className: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
  },
  interview: {
    label: "Interview",
    className: "bg-green-500/15 text-green-400 border-green-500/20",
  },
  offer: {
    label: "Offer",
    className: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  },
  accepted: {
    label: "Accepted",
    className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  },
  rejected: {
    label: "Rejected",
    className: "bg-red-500/15 text-red-400 border-red-500/20",
  },
  withdrawn: {
    label: "Withdrawn",
    className: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  },
  ghosted: {
    label: "Ghosted",
    className: "bg-gray-500/15 text-gray-400 border-gray-500/20",
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
