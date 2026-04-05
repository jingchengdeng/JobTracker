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
