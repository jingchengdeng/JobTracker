import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

const CONFIG_FILE = path.join(process.cwd(), "data", "model-config.json");

interface RoleConfig {
  provider: string;
  model: string;
  fallback: { provider: string; model: string } | null;
}

interface ModelConfig {
  default: RoleConfig;
  classifier: RoleConfig;
  embedding: RoleConfig;
  interview: RoleConfig;
  linkedin: RoleConfig;
}

const DEFAULT_CONFIG: ModelConfig = {
  default: { provider: "openai", model: "gpt-5.4", fallback: null },
  classifier: { provider: "openai", model: "gpt-4o-mini", fallback: null },
  embedding: { provider: "openai", model: "text-embedding-3-small", fallback: null },
  interview: { provider: "openai", model: "gpt-5.4-mini", fallback: null },
  linkedin: { provider: "openai", model: "gpt-4o-mini", fallback: null },
};

function migrateConfig(raw: Record<string, unknown>): ModelConfig {
  if ("default" in raw && typeof raw.default === "object" && raw.default !== null) {
    const cfg = raw as unknown as Partial<ModelConfig>;
    return {
      default: cfg.default ?? DEFAULT_CONFIG.default,
      classifier: cfg.classifier ?? DEFAULT_CONFIG.classifier,
      embedding: cfg.embedding ?? DEFAULT_CONFIG.embedding,
      interview: cfg.interview ?? DEFAULT_CONFIG.interview,
      linkedin: cfg.linkedin ?? DEFAULT_CONFIG.linkedin,
    };
  }
  return {
    default: {
      provider: "openai",
      model: (raw.defaultModel as string) || "gpt-5.4",
      fallback: null,
    },
    classifier: {
      provider: "openai",
      model: (raw.classifierModel as string) || "gpt-4o-mini",
      fallback: null,
    },
    embedding: {
      provider: "openai",
      model: (raw.embeddingModel as string) || "text-embedding-3-small",
      fallback: null,
    },
    interview: DEFAULT_CONFIG.interview,
    linkedin: DEFAULT_CONFIG.linkedin,
  };
}

async function readConfig(): Promise<ModelConfig> {
  try {
    const content = await fs.readFile(CONFIG_FILE, "utf-8");
    return migrateConfig(JSON.parse(content));
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

async function writeConfig(config: ModelConfig) {
  const dir = path.dirname(CONFIG_FILE);
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export async function GET() {
  return NextResponse.json(await readConfig());
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  const config: ModelConfig = {
    default: {
      provider: body.default?.provider ?? DEFAULT_CONFIG.default.provider,
      model: body.default?.model ?? DEFAULT_CONFIG.default.model,
      fallback: body.default?.fallback ?? null,
    },
    classifier: {
      provider: body.classifier?.provider ?? DEFAULT_CONFIG.classifier.provider,
      model: body.classifier?.model ?? DEFAULT_CONFIG.classifier.model,
      fallback: body.classifier?.fallback ?? null,
    },
    embedding: {
      provider: body.embedding?.provider ?? DEFAULT_CONFIG.embedding.provider,
      model: body.embedding?.model ?? DEFAULT_CONFIG.embedding.model,
      fallback: body.embedding?.fallback ?? null,
    },
    interview: {
      provider: body.interview?.provider ?? DEFAULT_CONFIG.interview.provider,
      model: body.interview?.model ?? DEFAULT_CONFIG.interview.model,
      fallback: body.interview?.fallback ?? null,
    },
    linkedin: {
      provider: body.linkedin?.provider ?? DEFAULT_CONFIG.linkedin.provider,
      model: body.linkedin?.model ?? DEFAULT_CONFIG.linkedin.model,
      fallback: body.linkedin?.fallback ?? null,
    },
  };
  await writeConfig(config);
  return NextResponse.json(config);
}
