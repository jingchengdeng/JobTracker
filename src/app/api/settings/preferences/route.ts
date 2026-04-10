import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { userPreferences } from "@/db/schema";
import { desc } from "drizzle-orm";

export async function GET() {
  await dbReady;
  const result = await db
    .select()
    .from(userPreferences)
    .orderBy(desc(userPreferences.createdAt));
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  await dbReady;
  const body = await request.json();

  if (!body.content?.trim()) {
    return NextResponse.json({ error: "content is required" }, { status: 400 });
  }

  const [result] = await db
    .insert(userPreferences)
    .values({ content: body.content.trim() })
    .returning();

  return NextResponse.json(result, { status: 201 });
}
