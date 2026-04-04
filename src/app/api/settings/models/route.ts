import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
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
}

const DEFAULT_CONFIG: ModelConfig = {
  default: { provider: "openai", model: "gpt-5.4", fallback: null },
  classifier: { provider: "openai", model: "gpt-4o-mini", fallback: null },
  embedding: { provider: "openai", model: "text-embedding-3-small", fallback: null },
};

function migrateConfig(raw: Record<string, unknown>): ModelConfig {
  if ("default" in raw && typeof raw.default === "object" && raw.default !== null) {
    return raw as unknown as ModelConfig;
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
  };
}

function readConfig(): ModelConfig {
  if (!fs.existsSync(CONFIG_FILE)) {
    return { ...DEFAULT_CONFIG };
  }
  const raw = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
  return migrateConfig(raw);
}

function writeConfig(config: ModelConfig) {
  const dir = path.dirname(CONFIG_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export async function GET() {
  return NextResponse.json(readConfig());
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  const config: ModelConfig = {
    default: {
      provider: body.default?.provider || DEFAULT_CONFIG.default.provider,
      model: body.default?.model || DEFAULT_CONFIG.default.model,
      fallback: body.default?.fallback || null,
    },
    classifier: {
      provider: body.classifier?.provider || DEFAULT_CONFIG.classifier.provider,
      model: body.classifier?.model || DEFAULT_CONFIG.classifier.model,
      fallback: body.classifier?.fallback || null,
    },
    embedding: {
      provider: body.embedding?.provider || DEFAULT_CONFIG.embedding.provider,
      model: body.embedding?.model || DEFAULT_CONFIG.embedding.model,
      fallback: body.embedding?.fallback || null,
    },
  };
  writeConfig(config);
  return NextResponse.json(config);
}
