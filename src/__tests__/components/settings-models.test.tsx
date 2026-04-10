import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { SettingsModels } from "@/components/settings-models";

const MOCK_PROVIDERS = {
  openai: {
    label: "OpenAI",
    auth: "api_key",
    chatModels: ["gpt-5.4", "gpt-4o-mini"],
    embeddingModels: ["text-embedding-3-small"],
  },
  "openai-codex": {
    label: "OpenAI Codex",
    auth: "oauth",
    chatModels: ["gpt-5.4"],
    embeddingModels: [],
  },
  anthropic: {
    label: "Anthropic",
    auth: "api_key",
    chatModels: ["claude-sonnet-4-6"],
    embeddingModels: [],
  },
};

const MOCK_CONFIG = {
  default: { provider: "openai", model: "gpt-5.4", fallback: null },
  classifier: { provider: "openai", model: "gpt-4o-mini", fallback: null },
  embedding: { provider: "openai", model: "text-embedding-3-small", fallback: null },
  interview: { provider: "openai", model: "gpt-5.4-mini", fallback: null },
  linkedin: { provider: "openai", model: "gpt-4o-mini", fallback: null },
};

const MOCK_AUTH_PROFILES = [
  { id: "openai:default", provider: "openai", type: "api_key" },
];

beforeEach(() => {
  vi.restoreAllMocks();
  global.fetch = vi.fn((url: string) => {
    if (url.includes("/providers")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_PROVIDERS),
      });
    }
    if (url.includes("/models")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_CONFIG),
      });
    }
    if (url.includes("/auth")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_AUTH_PROFILES),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  }) as unknown as typeof fetch;
});

describe("SettingsModels", () => {
  it("renders all five role cards after loading", async () => {
    render(<SettingsModels />);
    await waitFor(() => {
      expect(screen.getByText("Default Model")).toBeInTheDocument();
    });
    expect(screen.getByText("Classifier Model")).toBeInTheDocument();
    expect(screen.getByText("Embedding Model")).toBeInTheDocument();
    expect(screen.getByText("Interview Model")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn Search Model")).toBeInTheDocument();
  });

  it("renders save button", async () => {
    render(<SettingsModels />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    });
  });

  it("fetches providers, models, and auth on mount", async () => {
    render(<SettingsModels />);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(3);
    });
    const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.map(
      (c: string[]) => c[0]
    );
    expect(calls).toContain("/api/settings/providers");
    expect(calls).toContain("/api/settings/models");
    expect(calls).toContain("/api/settings/auth");
  });

  it("shows loading state initially", () => {
    render(<SettingsModels />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
