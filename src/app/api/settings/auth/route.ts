import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const AUTH_FILE = path.join(process.cwd(), "data", "auth-profiles.json");
const LOCK_DIR = AUTH_FILE + ".lk";

interface AuthProfile {
  type: "api_key" | "oauth";
  provider: string;
  key?: string;
  access?: string;
  refresh?: string;
  expires?: number;
  email?: string;
}

interface AuthStore {
  profiles: Record<string, AuthProfile>;
}

function ensureFile() {
  const dir = path.dirname(AUTH_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  if (!fs.existsSync(AUTH_FILE)) {
    fs.writeFileSync(AUTH_FILE, JSON.stringify({ profiles: {} }, null, 2));
  }
}

function readStore(): AuthStore {
  ensureFile();
  return JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
}

function writeStore(store: AuthStore) {
  ensureFile();
  fs.writeFileSync(AUTH_FILE, JSON.stringify(store, null, 2));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withLock<T>(fn: () => T): Promise<T> {
  ensureFile();
  const retries = 15;
  const minDelay = 50;
  const maxDelay = 500;

  for (let i = 0; i < retries; i++) {
    try {
      fs.mkdirSync(LOCK_DIR);
      break;
    } catch (err: any) {
      if (err.code !== "EEXIST") throw err;
      // Stale lock recovery
      try {
        const st = fs.statSync(LOCK_DIR);
        if (Date.now() - st.mtimeMs > 30_000) {
          fs.rmSync(LOCK_DIR, { recursive: true });
          continue;
        }
      } catch {
        continue;
      }
      if (i === retries - 1) throw new Error("Could not acquire auth file lock");
      await sleep(Math.min(minDelay * Math.pow(2, i), maxDelay));
    }
  }

  try {
    return fn();
  } finally {
    try {
      fs.rmSync(LOCK_DIR, { recursive: true });
    } catch {
      // Lock already released
    }
  }
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
    email: profile.email,
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

  await withLock(() => {
    const store = readStore();
    const id = `${provider}:default`;
    store.profiles[id] = { type: "api_key", provider, key };
    writeStore(store);
  });

  return NextResponse.json({ id: `${provider}:default`, provider, status: "active" }, { status: 201 });
}

export async function DELETE(request: NextRequest) {
  const { id } = await request.json();

  if (!id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }

  const removed = await withLock(() => {
    const store = readStore();
    if (!store.profiles[id]) return false;
    delete store.profiles[id];
    writeStore(store);
    return true;
  });

  if (!removed) {
    return NextResponse.json({ error: "Profile not found" }, { status: 404 });
  }

  return NextResponse.json({ success: true });
}
