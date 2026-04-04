import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { resumes } from "@/db/schema";
import { eq } from "drizzle-orm";
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

  // Delete the file from disk
  const filePath = path.join(process.cwd(), resume.filePath);
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }

  db.delete(resumes).where(eq(resumes.id, Number(id))).run();

  return NextResponse.json({ success: true });
}
