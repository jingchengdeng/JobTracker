import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { jobs } from "@/db/schema";
import { eq, like, or, and, desc, asc, sql, getTableColumns } from "drizzle-orm";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const status = params.get("status");
  const source = params.get("source");
  const url = params.get("url");
  const search = params.get("search");
  const sort = params.get("sort") || "createdAt";
  const order = params.get("order") || "desc";

  let query = db.select().from(jobs).$dynamic();

  const conditions = [];
  if (status) conditions.push(eq(jobs.status, status as any));
  if (source) conditions.push(eq(jobs.source, source as any));
  if (url) conditions.push(eq(jobs.url, url));
  if (search) {
    conditions.push(
      or(
        like(jobs.title, `%${search}%`),
        like(jobs.company, `%${search}%`)
      )!
    );
  }

  if (conditions.length > 0) {
    query = query.where(and(...conditions));
  }

  const columns = getTableColumns(jobs);
  const sortColumn = columns[sort as keyof typeof columns];
  if (sortColumn) {
    query = query.orderBy(order === "asc" ? asc(sortColumn) : desc(sortColumn));
  }

  const results = await query;
  return NextResponse.json(results);
}

export async function POST(request: NextRequest) {
  const body = await request.json();

  const result = db
    .insert(jobs)
    .values({
      ...body,
      interviewDates: body.interviewDates ?? null,
    })
    .returning()
    .get();

  return NextResponse.json(result, { status: 201 });
}
