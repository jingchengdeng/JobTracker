import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { goals } from "@/db/schema";
import { eq } from "drizzle-orm";

export async function GET() {
  const result = db.select().from(goals).all();
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  // Upsert: if a goal with the same type exists, update it
  const existing = db
    .select()
    .from(goals)
    .where(eq(goals.type, body.type))
    .get();

  if (existing) {
    const result = db
      .update(goals)
      .set({ target: body.target, periodStart: body.periodStart })
      .where(eq(goals.id, existing.id))
      .returning()
      .get();
    return NextResponse.json(result);
  }

  const result = db.insert(goals).values(body).returning().get();
  return NextResponse.json(result, { status: 201 });
}
