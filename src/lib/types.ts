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

export const AI_RUN_STATUSES = ["pending", "running", "completed", "failed"] as const;
export const AI_STEP_TYPES = ["jd_analysis", "gap_analysis", "suggestions", "rewrite"] as const;
export const AI_STEP_STATUSES = ["pending", "running", "completed", "failed"] as const;
export const AI_MESSAGE_ROLES = ["user", "assistant"] as const;
export const RESUME_FILE_TYPES = ["pdf", "docx"] as const;

export const INTERVIEW_STATUSES = ["planning", "active", "paused", "completed", "interrupted"] as const;
export const INTERVIEW_TYPES = ["behavioral", "technical", "system_design"] as const;
export const INTERVIEW_DIFFICULTIES = ["easy", "medium", "hard"] as const;
export const INTERVIEW_TURN_ROLES = ["interviewer", "candidate"] as const;

export type AiRunStatus = (typeof AI_RUN_STATUSES)[number];
export type AiStepType = (typeof AI_STEP_TYPES)[number];
export type AiStepStatus = (typeof AI_STEP_STATUSES)[number];
export type AiMessageRole = (typeof AI_MESSAGE_ROLES)[number];
export type ResumeFileType = (typeof RESUME_FILE_TYPES)[number];

export type InterviewStatus = (typeof INTERVIEW_STATUSES)[number];
export type InterviewType = (typeof INTERVIEW_TYPES)[number];
export type InterviewDifficulty = (typeof INTERVIEW_DIFFICULTIES)[number];
export type InterviewTurnRole = (typeof INTERVIEW_TURN_ROLES)[number];

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

export interface Resume {
  id: number;
  name: string;
  version: string | null;
  filePath: string;
  fileType: ResumeFileType;
  extractedText: string | null;
  lastIndexSignature: string | null;
  lastIndexStatus: IndexStatus | null;
  lastIndexError: string | null;
  createdAt: string;
}

export const INDEX_STATUSES = ["ok", "failed", "pending"] as const;
export type IndexStatus = (typeof INDEX_STATUSES)[number];

export interface EmbeddingResumeStatus {
  id: number;
  name: string;
  last_index_signature: string | null;
  last_index_status: IndexStatus | null;
  last_index_error: string | null;
}

export interface ReindexJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  target_signature: string;
  started_at: string;
  completed_at: string | null;
  total: number;
  succeeded: number[];
  failed: { resume_id: number | null; error: string }[];
  current_resume_id: number | null;
}

export interface EmbeddingStatus {
  active_signature: string | null;
  configured_signature: string;
  resumes: EmbeddingResumeStatus[];
  active_job: ReindexJob | null;
}

export interface UserPreference {
  id: number;
  content: string;
  createdAt: string;
}

export interface AiRun {
  id: number;
  jobId: number;
  resumeId: number;
  status: AiRunStatus;
  conversationSummary: string | null;
  error: string | null;
  createdAt: string;
  completedAt: string | null;
}

export interface AiStep {
  id: number;
  runId: number;
  stepType: AiStepType;
  status: AiStepStatus;
  result: string | null;
  version: number;
  createdAt: string;
  completedAt: string | null;
}

export interface AiMessage {
  id: number;
  runId: number;
  role: AiMessageRole;
  content: string;
  roundNumber: number;
  createdAt: string;
}

export interface RunSummary {
  id: number;
  resume_id: number;
  resume_name: string;
  resume_version: string | null;
  status: "pending" | "running" | "completed" | "failed";
  error: string | null;
  match_score: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface InterviewSession {
  id: number;
  jobId: number;
  resumeId: number | null;
  status: InterviewStatus;
  interviewType: InterviewType;
  difficulty: InterviewDifficulty;
  durationMinutes: number;
  focusArea: string | null;
  voice: string;
  createdAt: string;
  startedAt: string | null;
  endedAt: string | null;
}

export interface InterviewTurn {
  id: number;
  sessionId: number;
  turnNumber: number;
  role: InterviewTurnRole;
  text: string;
  audioDurationMs: number | null;
  planTopicRef: string | null;
  createdAt: string;
}

export interface InterviewResult {
  id: number;
  sessionId: number;
  overallScore: number;
  dimensionScoresJson: string;
  strengthsJson: string;
  improvementsJson: string;
  modelAnswersJson: string;
  summary: string;
  createdAt: string;
}

export interface InterviewSessionSummary {
  id: number;
  interview_type: string;
  difficulty: string;
  status: string;
  overall_score: number | null;
  created_at: string;
}
