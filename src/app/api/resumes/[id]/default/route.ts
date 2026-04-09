import { db } from "@/db";
import { resumes } from "@/db/schema";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";

export async function PATCH(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const resumeId = parseInt(id, 10);

  if (isNaN(resumeId)) {
    return NextResponse.json({ error: "Invalid resume ID" }, { status: 400 });
  }

  const resume = db
    .select({ id: resumes.id })
    .from(resumes)
    .where(eq(resumes.id, resumeId))
    .get();

  if (!resume) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  db.update(resumes).set({ isDefault: 0 }).run();
  db.update(resumes)
    .set({ isDefault: 1 })
    .where(eq(resumes.id, resumeId))
    .run();

  return NextResponse.json({ ok: true, resumeId });
}
