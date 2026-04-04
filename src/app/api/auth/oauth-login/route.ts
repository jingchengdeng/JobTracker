import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const SUPPORTED_PROVIDERS = ["openai-codex"];

export async function POST(request: NextRequest) {
  const { provider } = await request.json();

  if (!provider || !SUPPORTED_PROVIDERS.includes(provider)) {
    return NextResponse.json(
      { error: `Unsupported provider: ${provider}` },
      { status: 400 }
    );
  }

  const scriptPath = path.join(process.cwd(), "scripts", "oauth-login.mjs");

  try {
    const result = await new Promise<{ stdout: string; stderr: string }>(
      (resolve, reject) => {
        const child = spawn("node", [scriptPath, provider], {
          cwd: process.cwd(),
          timeout: 120_000,
        });

        let stdout = "";
        let stderr = "";

        child.stdout.on("data", (data) => {
          stdout += data.toString();
        });
        child.stderr.on("data", (data) => {
          stderr += data.toString();
        });

        child.on("close", (code) => {
          if (code === 0) {
            resolve({ stdout, stderr });
          } else {
            reject(new Error(stderr || `Script exited with code ${code}`));
          }
        });

        child.on("error", reject);
      }
    );

    const output = JSON.parse(result.stdout.trim());
    return NextResponse.json(output);
  } catch (err: any) {
    let detail = "OAuth login failed";
    try {
      const parsed = JSON.parse(err.message);
      detail = parsed.error || detail;
    } catch {
      detail = err.message || detail;
    }
    return NextResponse.json({ error: detail }, { status: 500 });
  }
}
