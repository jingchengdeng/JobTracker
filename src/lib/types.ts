export const JOB_STATUSES = [
  "saved",
  "applied",
  "phone_screen",
  "interview",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "ghosted",
] as const;

export const JOB_TYPES = [
  "full_time",
  "part_time",
  "contract",
  "internship",
] as const;

export const WORK_MODES = ["remote", "hybrid", "onsite"] as const;

export const SOURCES = [
  "linkedin",
  "indeed",
  "company_site",
  "referral",
  "other",
] as const;

export const GOAL_TYPES = ["weekly", "monthly"] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];
export type JobType = (typeof JOB_TYPES)[number];
export type WorkMode = (typeof WORK_MODES)[number];
export type Source = (typeof SOURCES)[number];
export type GoalType = (typeof GOAL_TYPES)[number];

export const STATUS_LABELS: Record<JobStatus, string> = {
  saved: "Saved",
  applied: "Applied",
  phone_screen: "Phone Screen",
  interview: "Interview",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  ghosted: "Ghosted",
};

export const TYPE_LABELS: Record<JobType, string> = {
  full_time: "Full Time",
  part_time: "Part Time",
  contract: "Contract",
  internship: "Internship",
};

export const MODE_LABELS: Record<WorkMode, string> = {
  remote: "Remote",
  hybrid: "Hybrid",
  onsite: "On-site",
};

export const SOURCE_LABELS: Record<Source, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  company_site: "Company Site",
  referral: "Referral",
  other: "Other",
};

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string | null;
  salaryMin: number | null;
  salaryMax: number | null;
  salaryCurrency: string | null;
  status: JobStatus;
  jobType: JobType | null;
  workMode: WorkMode | null;
  source: Source | null;
  contactName: string | null;
  contactEmail: string | null;
  resumeVersion: string | null;
  notes: string | null;
  priority: number | null;
  dateApplied: string | null;
  interviewDates: string[] | null;
  createdAt: string;
  updatedAt: string;
}
