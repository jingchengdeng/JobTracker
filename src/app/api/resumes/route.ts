import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { resumes } from "@/db/schema";
import { desc, eq } from "drizzle-orm";
import fs from "fs/promises";
import path from "path";

const UPLOAD_DIR = path.join(process.cwd(), "data", "resumes");

export async function GET() {
  await dbReady;
  const result = await db.select().from(resumes).orderBy(desc(resumes.createdAt));
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  await dbReady;
  const formData = await request.formData();
  const file = formData.get("file") as File | null;
  const name = formData.get("name") as string | null;
  const version = formData.get("version") as string | null;

  if (!file || !name) {
    return NextResponse.json({ error: "file and name are required" }, { status: 400 });
  }

  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext !== "pdf" && ext !== "docx") {
    return NextResponse.json({ error: "Only PDF and DOCX files are supported" }, { status: 400 });
  }

  await fs.mkdir(UPLOAD_DIR, { recursive: true });

  const buffer = Buffer.from(await file.arrayBuffer());
  const fileName = `${Date.now()}-${file.name}`;
  const filePath = path.join(UPLOAD_DIR, fileName);

  // Insert DB row first, then write file. If file write fails, remove the row.
  const [result] = await db
    .insert(resumes)
    .values({
      name,
      version: version || null,
      filePath: `data/resumes/${fileName}`,
      fileType: ext as "pdf" | "docx",
    })
    .returning();

  try {
    await fs.writeFile(filePath, buffer);
  } catch (err) {
    await db.delete(resumes).where(eq(resumes.id, result.id));
    throw err;
  }

  // Trigger text extraction in the Python backend (fire-and-forget)
  fetch(`http://localhost:8000/api/extract-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume_id: result.id, file_path: filePath }),
  }).catch(() => {
    // Non-fatal: extraction can be retried
  });

  return NextResponse.json(result, { status: 201 });
}
