import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { jobs } from "@/db/schema";
import { eq, sql } from "drizzle-orm";

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
  const [result] = await db
    .delete(jobs)
    .where(eq(jobs.id, Number(id)))
    .returning();

  if (!result) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
  return NextResponse.json({ success: true });
}
