import { NextRequest, NextResponse } from "next/server";
import { db, dbReady } from "@/db";
import { jobs } from "@/db/schema";
import { sql } from "drizzle-orm";

const ALLOWED_FIELDS = [
  "company",
  "location",
  "contact_name",
  "contact_email",
  "resume_version",
] as const;

export async function GET(request: NextRequest) {
  await dbReady;
  const field = request.nextUrl.searchParams.get("field");

  if (!field || !ALLOWED_FIELDS.includes(field as any)) {
    return NextResponse.json(
      { error: `Invalid field. Allowed: ${ALLOWED_FIELDS.join(", ")}` },
      { status: 400 }
    );
  }

  const results = await db
    .selectDistinct({ value: sql<string>`${sql.raw(field)}` })
    .from(jobs)
    .where(sql`${sql.raw(field)} IS NOT NULL AND ${sql.raw(field)} != ''`)
    .orderBy(sql`${sql.raw(field)}`);

  return NextResponse.json(results.map((r) => r.value));
}
