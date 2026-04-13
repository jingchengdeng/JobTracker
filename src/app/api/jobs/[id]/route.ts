import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import {
  jobs,
  aiRuns,
  aiMessages,
  pipelineEvents,
  interviewSessions,
  interviewTurns,
  interviewResults,
} from "@/db/schema";
import { eq, inArray, sql } from "drizzle-orm";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const [job] = await db.select().from(jobs).where(eq(jobs.id, Number(id)));

  if (!job) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
  return NextResponse.json(job);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const body = await request.json();

  const [result] = await db
    .update(jobs)
    .set({
      ...body,
      updatedAt: sql`(datetime('now'))`,
    })
    .where(eq(jobs.id, Number(id)))
    .returning();

  if (!result) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
  return NextResponse.json(result);
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const jobId = Number(id);

  const result = await db.transaction(async (tx) => {
    const runIds = tx.select({ id: aiRuns.id }).from(aiRuns).where(eq(aiRuns.jobId, jobId));
    const sessionIds = tx
      .select({ id: interviewSessions.id })
      .from(interviewSessions)
      .where(eq(interviewSessions.jobId, jobId));

    // delete leaf tables first
    await tx.delete(interviewResults).where(inArray(interviewResults.sessionId, sessionIds));
    await tx.delete(interviewTurns).where(inArray(interviewTurns.sessionId, sessionIds));
    await tx.delete(aiMessages).where(inArray(aiMessages.runId, runIds));
    await tx.delete(pipelineEvents).where(eq(pipelineEvents.jobId, jobId));

    // delete intermediate tables
    await tx.delete(interviewSessions).where(eq(interviewSessions.jobId, jobId));
    await tx.delete(aiRuns).where(eq(aiRuns.jobId, jobId));

    // delete the job
    const [deleted] = await tx.delete(jobs).where(eq(jobs.id, jobId)).returning();
    return deleted;
  });

  if (!result) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
  return NextResponse.json({ success: true });
}
