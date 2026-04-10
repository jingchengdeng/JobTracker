import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { resumes, aiRuns, aiSteps, aiMessages } from "@/db/schema";
import { eq, inArray } from "drizzle-orm";
import fs from "fs";
import path from "path";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const resume = db.select().from(resumes).where(eq(resumes.id, Number(id))).get();

  if (!resume) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  return NextResponse.json(resume);
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const resume = db.select().from(resumes).where(eq(resumes.id, Number(id))).get();

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
  db.transaction((tx) => {
    const runs = tx
      .select({ id: aiRuns.id })
      .from(aiRuns)
      .where(eq(aiRuns.resumeId, resumeId))
      .all();
    const runIds = runs.map((r) => r.id);

    if (runIds.length > 0) {
      tx.delete(aiMessages).where(inArray(aiMessages.runId, runIds)).run();
      tx.delete(aiSteps).where(inArray(aiSteps.runId, runIds)).run();
      tx.delete(aiRuns).where(inArray(aiRuns.id, runIds)).run();
    }

    tx.delete(resumes).where(eq(resumes.id, resumeId)).run();
  });

  // Delete file after DB transaction succeeds
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }

  return NextResponse.json({ success: true });
}
