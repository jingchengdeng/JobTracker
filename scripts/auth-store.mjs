import { readFileSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { dirname, join } from "path";
import lockfile from "proper-lockfile";

const AUTH_FILE = join(process.cwd(), "data", "auth-profiles.json");
const LOCK_OPTIONS = { retries: { retries: 5, minTimeout: 100, maxTimeout: 1000 } };

export function ensureDir() {
  const dir = dirname(AUTH_FILE);
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  if (!existsSync(AUTH_FILE)) {
    writeFileSync(AUTH_FILE, JSON.stringify({ profiles: {} }, null, 2));
  }
}

export function readStore() {
  ensureDir();
  return JSON.parse(readFileSync(AUTH_FILE, "utf-8"));
}

export function writeStore(store) {
  ensureDir();
  writeFileSync(AUTH_FILE, JSON.stringify(store, null, 2));
}

export async function withLock(fn) {
  ensureDir();
  const release = await lockfile.lock(AUTH_FILE, LOCK_OPTIONS);
  try {
    return await fn();
  } finally {
    await release();
  }
}

export { AUTH_FILE };
