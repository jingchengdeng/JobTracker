import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";
import { sql } from "drizzle-orm";
import {
  JOB_STATUSES,
  JOB_TYPES,
  WORK_MODES,
  SOURCES,
  GOAL_TYPES,
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
