import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { resumes } from "@/db/schema";
import { desc } from "drizzle-orm";
import fs from "fs";
import path from "path";

const UPLOAD_DIR = path.join(process.cwd(), "data", "resumes");

export async function GET() {
  const result = db.select().from(resumes).orderBy(desc(resumes.createdAt)).all();
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
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

  if (!fs.existsSync(UPLOAD_DIR)) {
    fs.mkdirSync(UPLOAD_DIR, { recursive: true });
  }

  // Save the file
  const buffer = Buffer.from(await file.arrayBuffer());
  const fileName = `${Date.now()}-${file.name}`;
  const filePath = path.join(UPLOAD_DIR, fileName);
  fs.writeFileSync(filePath, buffer);

  const result = db
    .insert(resumes)
    .values({
      name,
      version: version || null,
      filePath: `data/resumes/${fileName}`,
      fileType: ext as "pdf" | "docx",
    })
    .returning()
    .get();

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
