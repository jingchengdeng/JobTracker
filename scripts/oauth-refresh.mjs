import { refreshOpenAICodexToken } from "@mariozechner/pi-ai/oauth";
import { readStore, writeStore, withLock } from "./auth-store.mjs";

const provider = process.argv[2];
if (provider !== "openai-codex") {
  console.error(JSON.stringify({ error: `Unsupported refresh provider: ${provider}` }));
  process.exit(1);
}

try {
  const profileId = `${provider}:default`;

  const store = readStore();
  const profile = store.profiles[profileId];

  if (!profile || profile.type !== "oauth") {
    console.error(JSON.stringify({ error: `No OAuth profile found for ${provider}` }));
    process.exit(1);
  }

  if (!profile.refresh) {
    console.error(JSON.stringify({ error: "No refresh token available. Re-login required." }));
    process.exit(1);
  }

  const refreshed = await refreshOpenAICodexToken(profile.refresh);

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
