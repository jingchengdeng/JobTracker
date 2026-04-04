import { refreshOpenAICodexToken } from "@mariozechner/pi-ai/oauth";
import { readStore, writeStore, withLock } from "./auth-store.mjs";

const provider = process.argv[2];
if (provider !== "openai-codex") {
  console.error(JSON.stringify({ error: `Unsupported refresh provider: ${provider}` }));
  process.exit(1);
}

try {
  const profileId = `${provider}:default`;

  // Read refresh token under lock to avoid TOCTOU race
  let refreshToken;
  await withLock(() => {
    const store = readStore();
    const profile = store.profiles[profileId];

    if (!profile || profile.type !== "oauth") {
      throw new Error(`No OAuth profile found for ${provider}`);
    }
    if (!profile.refresh) {
      throw new Error("No refresh token available. Re-login required.");
    }
    refreshToken = profile.refresh;
  });

  // Network call outside lock to avoid holding it during I/O
  const refreshed = await refreshOpenAICodexToken(refreshToken);

  // Write updated tokens under lock
  await withLock(() => {
    const current = readStore();
    current.profiles[profileId] = {
      ...current.profiles[profileId],
      access: refreshed.access,
      refresh: refreshed.refresh,
      expires: refreshed.expires,
    };
    writeStore(current);
  });

  console.log(JSON.stringify({ status: "refreshed", provider }));
} catch (err) {
  console.error(JSON.stringify({ error: err.message || String(err) }));
  process.exit(1);
}
