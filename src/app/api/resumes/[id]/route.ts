import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { resumes, aiRuns, aiSteps, aiMessages } from "@/db/schema";
import { eq, inArray } from "drizzle-orm";
import fs from "fs/promises";
import path from "path";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const [resume] = await db.select().from(resumes).where(eq(resumes.id, Number(id)));

  if (!resume) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  return NextResponse.json(resume);
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const [resume] = await db.select().from(resumes).where(eq(resumes.id, Number(id)));

  if (!resume) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  const resumeId = Number(id);
  const filePath = path.join(process.cwd(), resume.filePath);

  // Drop vector chunks from the Python RAG store. Non-fatal: if the backend is
  // down we'd rather finish the DB cleanup than leave a half-deleted resume.
  try {
    await fetch(`http://localhost:8000/api/resumes/${resumeId}/chunks`, {
      method: "DELETE",
    });
  } catch {
    // backend unreachable, orphans will need manual cleanup
  }

  // Cascade delete dependent AI records so the FK constraint on ai_runs.resume_id
  // doesn't block removal. Wrap in a transaction for atomicity.
  await db.transaction(async (tx) => {
    const runs = await tx
      .select({ id: aiRuns.id })
      .from(aiRuns)
      .where(eq(aiRuns.resumeId, resumeId));
    const runIds = runs.map((r) => r.id);

    if (runIds.length > 0) {
      await tx.delete(aiMessages).where(inArray(aiMessages.runId, runIds));
      await tx.delete(aiSteps).where(inArray(aiSteps.runId, runIds));
      await tx.delete(aiRuns).where(inArray(aiRuns.id, runIds));
    }

    await tx.delete(resumes).where(eq(resumes.id, resumeId));
  });

  // Delete file after DB transaction succeeds
  try {
    await fs.unlink(filePath);
  } catch {
    // File already deleted or never existed
  }

  return NextResponse.json({ success: true });
}
