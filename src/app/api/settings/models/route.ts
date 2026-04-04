import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const CONFIG_FILE = path.join(process.cwd(), "data", "model-config.json");

interface ModelConfig {
  defaultModel: string;
  classifierModel: string;
  embeddingModel: string;
}

const DEFAULT_CONFIG: ModelConfig = {
  defaultModel: "gpt-4o",
  classifierModel: "gpt-4o-mini",
  embeddingModel: "text-embedding-3-small",
};

function readConfig(): ModelConfig {
  if (!fs.existsSync(CONFIG_FILE)) {
    return { ...DEFAULT_CONFIG };
  }
  return JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
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
  const current = readConfig();
  const updated = { ...current, ...body };
  writeConfig(updated);
  return NextResponse.json(updated);
}
