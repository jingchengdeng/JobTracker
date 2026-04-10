import { db, dbReady } from "@/db";
import { resumes } from "@/db/schema";
import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";

export async function PATCH(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  await dbReady;
  const { id } = await params;
  const resumeId = parseInt(id, 10);

  if (isNaN(resumeId)) {
    return NextResponse.json({ error: "Invalid resume ID" }, { status: 400 });
  }

  const found = await db.transaction(async (tx) => {
    const [resume] = await tx
      .select({ id: resumes.id })
      .from(resumes)
      .where(eq(resumes.id, resumeId));

    if (!resume) return false;

    await tx.update(resumes).set({ isDefault: 0 });
    await tx.update(resumes)
      .set({ isDefault: 1 })
      .where(eq(resumes.id, resumeId));
    return true;
  });

  if (!found) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  return NextResponse.json({ ok: true, resumeId });
}
