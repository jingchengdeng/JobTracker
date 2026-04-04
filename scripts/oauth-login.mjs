import { loginOpenAICodex } from "@mariozechner/pi-ai/oauth";
import open from "open";
import { readStore, writeStore, withLock } from "./auth-store.mjs";

const provider = process.argv[2];
if (provider !== "openai-codex") {
  console.error(JSON.stringify({ error: `Unsupported OAuth provider: ${provider}` }));
  process.exit(1);
}

try {
  const creds = await loginOpenAICodex({
    onAuth: async ({ url }) => {
      await open(url);
    },
    onPrompt: async ({ message }) => {
      // For local desktop use, the browser callback handles this automatically.
      // If the callback doesn't fire, pi-ai falls back to prompting.
      // In that case we can't read stdin from a spawned process, so we fail.
      throw new Error("Manual code entry not supported. Retry the login flow.");
    },
    onProgress: () => {},
  });

  if (!creds) {
    console.error(JSON.stringify({ error: "Login cancelled or returned no credentials" }));
    process.exit(1);
  }

  await withLock(() => {
    const store = readStore();
    store.profiles[`${provider}:default`] = {
      type: "oauth",
      provider,
      access: creds.access,
      refresh: creds.refresh,
      expires: creds.expires,
      email: creds.email || null,
    };
    writeStore(store);
  });

  console.log(JSON.stringify({ status: "connected", provider, email: creds.email || null }));
  // Force exit: pi-ai's OAuth server holds keep-alive connections open,
  // preventing natural process termination.
  process.exit(0);
} catch (err) {
  console.error(JSON.stringify({ error: err.message || String(err) }));
  process.exit(1);
}
