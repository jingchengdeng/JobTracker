import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { userPreferences } from "@/db/schema";
import { desc } from "drizzle-orm";

export async function GET() {
  const result = db
    .select()
    .from(userPreferences)
    .orderBy(desc(userPreferences.createdAt))
    .all();
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  if (!body.content?.trim()) {
    return NextResponse.json({ error: "content is required" }, { status: 400 });
  }

  const result = db
    .insert(userPreferences)
    .values({ content: body.content.trim() })
    .returning()
    .get();

  return NextResponse.json(result, { status: 201 });
}
