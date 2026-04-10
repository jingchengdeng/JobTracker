import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { goals } from "@/db/schema";
import { eq } from "drizzle-orm";

export async function GET() {
  await dbReady;
  const result = await db.select().from(goals);
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  await dbReady;
  const body = await request.json();

  // Upsert: if a goal with the same type exists, update it
  const [existing] = await db
    .select()
    .from(goals)
    .where(eq(goals.type, body.type));

  if (existing) {
    const [result] = await db
      .update(goals)
      .set({ target: body.target, periodStart: body.periodStart })
      .where(eq(goals.id, existing.id))
      .returning();
    return NextResponse.json(result);
  }

  const [result] = await db.insert(goals).values(body).returning();
  return NextResponse.json(result, { status: 201 });
}
