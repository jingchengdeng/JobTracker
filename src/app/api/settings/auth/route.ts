import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const AUTH_FILE = path.join(process.cwd(), "data", "auth-profiles.json");

interface AuthProfile {
  type: "api_key" | "oauth";
  provider: string;
  key?: string;
  access?: string;
  refresh?: string;
  expires?: number;
}

interface AuthStore {
  profiles: Record<string, AuthProfile>;
}

function readStore(): AuthStore {
  if (!fs.existsSync(AUTH_FILE)) {
    return { profiles: {} };
  }
  return JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
}

function writeStore(store: AuthStore) {
  const dir = path.dirname(AUTH_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(AUTH_FILE, JSON.stringify(store, null, 2));
}

function maskKey(key: string): string {
  if (key.length <= 8) return "****";
  return key.slice(0, 7) + "..." + key.slice(-3);
}

export async function GET() {
  const store = readStore();
  const masked = Object.entries(store.profiles).map(([id, profile]) => ({
    id,
    type: profile.type,
    provider: profile.provider,
    maskedKey: profile.key ? maskKey(profile.key) : undefined,
    status:
      profile.type === "oauth"
        ? profile.expires && profile.expires < Date.now()
          ? "expired"
          : "connected"
        : "active",
  }));
  return NextResponse.json(masked);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { provider, key } = body;

  if (!provider || !key) {
    return NextResponse.json(
      { error: "provider and key are required" },
      { status: 400 }
    );
  }

  const store = readStore();
  const id = `${provider}:default`;
  store.profiles[id] = {
    type: "api_key",
    provider,
    key,
  };
  writeStore(store);

  return NextResponse.json({ id, provider, status: "active" }, { status: 201 });
}

export async function DELETE(request: NextRequest) {
  const { id } = await request.json();

  if (!id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }

  const store = readStore();
  if (!store.profiles[id]) {
    return NextResponse.json({ error: "Profile not found" }, { status: 404 });
  }

  delete store.profiles[id];
  writeStore(store);

  return NextResponse.json({ success: true });
}
