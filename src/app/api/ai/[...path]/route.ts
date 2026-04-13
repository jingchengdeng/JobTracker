import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.AI_BACKEND_URL || "http://localhost:8000";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxyRequest(request: NextRequest) {
  const path = request.nextUrl.pathname.replace(/^\/api\/ai/, "/api");
  const url = `${BACKEND_URL}${path}${request.nextUrl.search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");

  const init: RequestInit = {
    method: request.method,
    headers,
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  const res = await fetch(url, init);
  const contentType = res.headers.get("content-type") || "application/json";

  if (contentType.startsWith("text/event-stream")) {
    return new Response(res.body, {
      status: res.status,
      headers: {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        "connection": "keep-alive",
      },
    });
  }

  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "content-type": contentType },
  });
}

export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const DELETE = proxyRequest;
