import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, statSync } from "fs";
import { dirname, join } from "path";

const AUTH_FILE = join(process.cwd(), "data", "auth-profiles.json");
const LOCK_DIR = AUTH_FILE + ".lk";

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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function acquireLock(retries = 15, minDelay = 50, maxDelay = 500) {
  ensureDir();
  for (let i = 0; i < retries; i++) {
    try {
      mkdirSync(LOCK_DIR);
      return;
    } catch (err) {
      if (err.code !== "EEXIST") throw err;
      // Check for stale lock (older than 30 seconds)
      try {
        const st = statSync(LOCK_DIR);
        if (Date.now() - st.mtimeMs > 30_000) {
          rmSync(LOCK_DIR, { recursive: true });
          continue;
        }
      } catch {
        continue; // Lock was released between check and stat
      }
      const delay = Math.min(minDelay * Math.pow(2, i), maxDelay);
      await sleep(delay);
    }
  }
  throw new Error("Could not acquire lock after retries");
}

function releaseLock() {
  try {
    rmSync(LOCK_DIR, { recursive: true });
  } catch {
    // Lock already released
  }
}

export async function withLock(fn) {
  await acquireLock();
  try {
    return await fn();
  } finally {
    releaseLock();
  }
}

export { AUTH_FILE };
