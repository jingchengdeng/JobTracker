import { NextResponse } from "next/server";

const PROVIDERS: Record<
  string,
  {
    label: string;
    auth: string;
    chatModels: string[];
    embeddingModels: string[];
  }
> = {
  openai: {
    label: "OpenAI",
    auth: "api_key",
    chatModels: [
      "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.3",
      "gpt-5.2-pro", "gpt-4.1", "gpt-4.1-mini", "gpt-4o",
      "gpt-4o-mini", "o3-mini",
    ],
    embeddingModels: ["text-embedding-3-small", "text-embedding-3-large"],
  },
  "openai-codex": {
    label: "OpenAI Codex",
    auth: "oauth",
    chatModels: ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5.3-codex-spark"],
    embeddingModels: [],
  },
  anthropic: {
    label: "Anthropic",
    auth: "api_key",
    chatModels: ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
    embeddingModels: [],
  },
  kimi: {
    label: "Kimi",
    auth: "api_key",
    chatModels: ["kimi-k2.5", "kimi-k2", "kimi-k2-thinking"],
    embeddingModels: [],
  },
  openrouter: {
    label: "OpenRouter",
    auth: "api_key",
    chatModels: [],
    embeddingModels: ["text-embedding-3-small", "text-embedding-3-large"],
  },
};

export async function GET() {
  return NextResponse.json(PROVIDERS);
}
