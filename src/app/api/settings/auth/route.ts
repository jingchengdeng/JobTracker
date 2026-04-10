import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
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

async function ensureFile() {
  const dir = path.dirname(AUTH_FILE);
  await fs.mkdir(dir, { recursive: true });
  try {
    await fs.access(AUTH_FILE);
  } catch {
    await fs.writeFile(AUTH_FILE, JSON.stringify({ profiles: {} }, null, 2));
  }
}

async function readStore(): Promise<AuthStore> {
  await ensureFile();
  const content = await fs.readFile(AUTH_FILE, "utf-8");
  return JSON.parse(content);
}

async function writeStore(store: AuthStore) {
  await ensureFile();
  await fs.writeFile(AUTH_FILE, JSON.stringify(store, null, 2));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function withLock<T>(fn: () => T | Promise<T>): Promise<T> {
  await ensureFile();
  const retries = 15;
  const minDelay = 50;
  const maxDelay = 500;

  for (let i = 0; i < retries; i++) {
    try {
      await fs.mkdir(LOCK_DIR);
      break;
    } catch (err: any) {
      if (err.code !== "EEXIST") throw err;
      // Stale lock recovery
      try {
        const st = await fs.stat(LOCK_DIR);
        if (Date.now() - st.mtimeMs > 30_000) {
          await fs.rm(LOCK_DIR, { recursive: true });
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
    return await fn();
  } finally {
    try {
      await fs.rm(LOCK_DIR, { recursive: true });
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
  const store = await readStore();
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

  await withLock(async () => {
    const store = await readStore();
    const id = `${provider}:default`;
    store.profiles[id] = { type: "api_key", provider, key };
    await writeStore(store);
  });

  return NextResponse.json({ id: `${provider}:default`, provider, status: "active" }, { status: 201 });
}

export async function DELETE(request: NextRequest) {
  const { id } = await request.json();

  if (!id) {
    return NextResponse.json({ error: "id is required" }, { status: 400 });
  }

  const removed = await withLock(async () => {
    const store = await readStore();
    if (!store.profiles[id]) return false;
    delete store.profiles[id];
    await writeStore(store);
    return true;
  });

  if (!removed) {
    return NextResponse.json({ error: "Profile not found" }, { status: 404 });
  }

  return NextResponse.json({ success: true });
}
