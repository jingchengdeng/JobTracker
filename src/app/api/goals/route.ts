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

  const result = await db.transaction(async (tx) => {
    const [existing] = await tx
      .select()
      .from(goals)
      .where(eq(goals.type, body.type));

    if (existing) {
      const [updated] = await tx
        .update(goals)
        .set({ target: body.target, periodStart: body.periodStart })
        .where(eq(goals.id, existing.id))
        .returning();
      return { row: updated, created: false };
    }

    const [created] = await tx.insert(goals).values(body).returning();
    return { row: created, created: true };
  });

  return NextResponse.json(result.row, { status: result.created ? 201 : 200 });
}
