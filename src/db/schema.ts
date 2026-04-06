import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";
import {
  JOB_STATUSES,
  JOB_TYPES,
  WORK_MODES,
  SOURCES,
  GOAL_TYPES,
  AI_RUN_STATUSES,
  AI_STEP_TYPES,
  AI_STEP_STATUSES,
  AI_MESSAGE_ROLES,
  RESUME_FILE_TYPES,
  INTERVIEW_STATUSES,
  INTERVIEW_TYPES,
  INTERVIEW_DIFFICULTIES,
  INTERVIEW_TURN_ROLES,
} from "@/lib/types";

export const jobs = sqliteTable("jobs", {
  id: integer().primaryKey({ autoIncrement: true }),
  title: text().notNull(),
  company: text().notNull(),
  location: text(),
  url: text(),
  description: text(),
  salaryMin: integer("salary_min"),
  salaryMax: integer("salary_max"),
  salaryCurrency: text("salary_currency").default("USD"),
  status: text({ enum: JOB_STATUSES }).notNull().default("saved"),
  jobType: text("job_type", { enum: JOB_TYPES }),
  workMode: text("work_mode", { enum: WORK_MODES }),
  source: text({ enum: SOURCES }),
  contactName: text("contact_name"),
  contactEmail: text("contact_email"),
  resumeVersion: text("resume_version"),
  notes: text(),
  priority: integer(),
  dateApplied: text("date_applied"),
  interviewDates: text("interview_dates", { mode: "json" }).$type<string[]>(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
  updatedAt: text("updated_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const goals = sqliteTable("goals", {
  id: integer().primaryKey({ autoIncrement: true }),
  type: text({ enum: GOAL_TYPES }).notNull(),
  target: integer().notNull(),
  periodStart: text("period_start").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const resumes = sqliteTable("resumes", {
  id: integer().primaryKey({ autoIncrement: true }),
  name: text().notNull(),
  version: text(),
  filePath: text("file_path").notNull(),
  fileType: text("file_type", { enum: RESUME_FILE_TYPES }).notNull(),
  extractedText: text("extracted_text"),
  lastIndexSignature: text("last_index_signature"),
  lastIndexStatus: text("last_index_status", { enum: ["ok", "failed", "pending"] }),
  lastIndexError: text("last_index_error"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const embeddingState = sqliteTable("embedding_state", {
  id: integer().primaryKey(),
  activeSignature: text("active_signature"),
  updatedAt: text("updated_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const userPreferences = sqliteTable("user_preferences", {
  id: integer().primaryKey({ autoIncrement: true }),
  content: text().notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const aiRuns = sqliteTable("ai_runs", {
  id: integer().primaryKey({ autoIncrement: true }),
  jobId: integer("job_id")
    .notNull()
    .references(() => jobs.id),
  resumeId: integer("resume_id")
    .notNull()
    .references(() => resumes.id),
  status: text({ enum: AI_RUN_STATUSES }).notNull().default("pending"),
  conversationSummary: text("conversation_summary"),
  error: text(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
  completedAt: text("completed_at"),
});

export const aiSteps = sqliteTable("ai_steps", {
  id: integer().primaryKey({ autoIncrement: true }),
  runId: integer("run_id")
    .notNull()
    .references(() => aiRuns.id),
  stepType: text("step_type", { enum: AI_STEP_TYPES }).notNull(),
  status: text({ enum: AI_STEP_STATUSES }).notNull().default("pending"),
  result: text(),
  version: integer().notNull().default(1),
  roundNumber: integer("round_number").notNull().default(0),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
  completedAt: text("completed_at"),
});

export const aiMessages = sqliteTable("ai_messages", {
  id: integer().primaryKey({ autoIncrement: true }),
  runId: integer("run_id")
    .notNull()
    .references(() => aiRuns.id),
  role: text({ enum: AI_MESSAGE_ROLES }).notNull(),
  content: text().notNull(),
  roundNumber: integer("round_number").notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const interviewSessions = sqliteTable("interview_sessions", {
  id: integer().primaryKey({ autoIncrement: true }),
  jobId: integer("job_id")
    .notNull()
    .references(() => jobs.id),
  resumeId: integer("resume_id").references(() => resumes.id),
  status: text({ enum: INTERVIEW_STATUSES }).notNull().default("planning"),
  interviewType: text("interview_type", { enum: INTERVIEW_TYPES }).notNull(),
  difficulty: text({ enum: INTERVIEW_DIFFICULTIES }).notNull(),
  durationMinutes: integer("duration_minutes").notNull(),
  focusArea: text("focus_area"),
  voice: text().notNull().default("nova"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
  startedAt: text("started_at"),
  endedAt: text("ended_at"),
});

export const interviewTurns = sqliteTable("interview_turns", {
  id: integer().primaryKey({ autoIncrement: true }),
  sessionId: integer("session_id")
    .notNull()
    .references(() => interviewSessions.id),
  turnNumber: integer("turn_number").notNull(),
  role: text({ enum: INTERVIEW_TURN_ROLES }).notNull(),
  text: text().notNull(),
  audioDurationMs: integer("audio_duration_ms"),
  planTopicRef: text("plan_topic_ref"),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const interviewResults = sqliteTable("interview_results", {
  id: integer().primaryKey({ autoIncrement: true }),
  sessionId: integer("session_id")
    .notNull()
    .references(() => interviewSessions.id),
  overallScore: integer("overall_score").notNull(),
  dimensionScoresJson: text("dimension_scores_json").notNull(),
  strengthsJson: text("strengths_json").notNull(),
  improvementsJson: text("improvements_json").notNull(),
  modelAnswersJson: text("model_answers_json").notNull(),
  summary: text().notNull(),
  createdAt: text("created_at")
    .notNull()
    .default(sql`(datetime('now'))`),
});
