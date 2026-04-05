import { NextRequest, NextResponse } from "next/server";
import { execFile } from "child_process";

const SUPPORTED_PROVIDERS = ["openai-codex"];

function getScriptPath(): string {
  // Construct path at runtime to prevent Turbopack from analyzing it as a module import
  const parts = [process.cwd(), "scripts", "oauth-login.mjs"];
  return parts.join("/");
}

export async function POST(request: NextRequest) {
  const { provider } = await request.json();

  if (!provider || !SUPPORTED_PROVIDERS.includes(provider)) {
    return NextResponse.json(
      { error: `Unsupported provider: ${provider}` },
      { status: 400 }
    );
  }

  try {
    const result = await new Promise<{ stdout: string; stderr: string }>(
      (resolve, reject) => {
        execFile(
          "node",
          [getScriptPath(), provider],
          { cwd: process.cwd(), timeout: 120_000 },
          (error, stdout, stderr) => {
            if (error) {
              reject(new Error(stderr || error.message));
            } else {
              resolve({ stdout, stderr });
            }
          }
        );
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
