import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.AI_BACKEND_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  const { provider } = await params;
  const code = request.nextUrl.searchParams.get("code");

  if (!code) {
    return NextResponse.json({ error: "Missing authorization code" }, { status: 400 });
  }

  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, code }),
    });

    if (!res.ok) {
      const err = await res.json();
      return NextResponse.json({ error: err.detail || "Token exchange failed" }, { status: 500 });
    }

    return NextResponse.redirect(new URL("/settings", request.url));
  } catch {
    return NextResponse.json({ error: "Failed to connect to backend" }, { status: 500 });
  }
}
