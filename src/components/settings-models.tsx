"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface FallbackConfig {
  provider: string;
  model: string;
}

interface RoleConfig {
  provider: string;
  model: string;
  fallback: FallbackConfig | null;
}

interface ModelConfig {
  default: RoleConfig;
  classifier: RoleConfig;
  embedding: RoleConfig;
  interview: RoleConfig;
}

interface ProviderInfo {
  label: string;
  auth: string;
  chatModels: string[];
  embeddingModels: string[];
}

type ProvidersMap = Record<string, ProviderInfo>;

const ROLE_LABELS: Record<string, { title: string; description: string }> = {
  default: {
    title: "Default Model",
    description:
      "Used for general tasks like drafting cover letters and summarizing job descriptions.",
  },
  classifier: {
    title: "Classifier Model",
    description: "Lightweight model used to classify and tag job postings quickly.",
  },
  embedding: {
    title: "Embedding Model",
    description:
      "Generates vector embeddings for semantic search across resumes and job postings.",
  },
  interview: {
    title: "Interview Model",
    description:
      "Powers the mock interview pipeline — generates questions, evaluates answers, and produces feedback.",
  },
};

function ModelSelect({
  providers,
  role,
  isEmbedding,
  config,
  onChange,
  authProfiles,
}: {
  providers: ProvidersMap;
  role: string;
  isEmbedding: boolean;
  config: RoleConfig;
  onChange: (updated: RoleConfig) => void;
  authProfiles: Set<string>;
}) {
  const [customModel, setCustomModel] = useState(false);

  const availableProviders = Object.entries(providers).filter(([, p]) =>
    isEmbedding ? p.embeddingModels.length > 0 : true
  );

  const currentProvider = providers[config.provider];
  const modelList = isEmbedding
    ? currentProvider?.embeddingModels ?? []
    : currentProvider?.chatModels ?? [];
  const isCustomEntry = modelList.length === 0 || customModel;

  function handleProviderChange(providerId: string | null) {
    if (!providerId) return;
    const prov = providers[providerId];
    const models = isEmbedding ? prov.embeddingModels : prov.chatModels;
    const firstModel = models[0] || "";
    setCustomModel(false);
    onChange({ ...config, provider: providerId, model: firstModel });
  }

  function handleModelChange(value: string | null) {
    if (!value) return;
    if (value === "__custom__") {
      setCustomModel(true);
      onChange({ ...config, model: "" });
    } else {
      setCustomModel(false);
      onChange({ ...config, model: value });
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Provider</Label>
          <Select value={config.provider} onValueChange={handleProviderChange}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {availableProviders.map(([id, p]) => (
                <SelectItem key={id} value={id} disabled={!authProfiles.has(id)}>
                  {p.label}
                  {!authProfiles.has(id) && " (no credentials)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Model</Label>
          {isCustomEntry ? (
            <Input
              value={config.model}
              onChange={(e) => onChange({ ...config, model: e.target.value })}
              placeholder="Enter model name"
            />
          ) : (
            <Select value={config.model} onValueChange={handleModelChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {modelList.map((m) => (
                  <SelectItem key={m} value={m}>
                    {m}
                  </SelectItem>
                ))}
                <SelectItem value="__custom__">Custom...</SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>
      </div>
    </div>
  );
}

function RoleCard({
  role,
  providers,
  config,
  onChange,
  authProfiles,
}: {
  role: string;
  providers: ProvidersMap;
  config: RoleConfig;
  onChange: (updated: RoleConfig) => void;
  authProfiles: Set<string>;
}) {
  const info = ROLE_LABELS[role];
  const isEmbedding = role === "embedding";
  const [showFallback, setShowFallback] = useState(!!config.fallback);

  function handleFallbackToggle() {
    if (showFallback) {
      onChange({ ...config, fallback: null });
      setShowFallback(false);
    } else {
      const firstProvider = Object.keys(providers)[0];
      const prov = providers[firstProvider];
      const models = isEmbedding ? prov.embeddingModels : prov.chatModels;
      onChange({
        ...config,
        fallback: { provider: firstProvider, model: models[0] || "" },
      });
      setShowFallback(true);
    }
  }

  return (
    <Card className="p-4 space-y-4">
      <div>
        <h3 className="font-medium">{info.title}</h3>
        <p className="text-xs text-muted-foreground">{info.description}</p>
      </div>

      <ModelSelect
        providers={providers}
        role={role}
        isEmbedding={isEmbedding}
        config={config}
        onChange={(updated) => onChange({ ...updated, fallback: config.fallback })}
        authProfiles={authProfiles}
      />

      <div className="border-t pt-3">
        <button
          type="button"
          onClick={handleFallbackToggle}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {showFallback ? "Remove fallback" : "+ Add fallback"}
        </button>

        {showFallback && config.fallback && (
          <div className="mt-3">
            <ModelSelect
              providers={providers}
              role={role}
              isEmbedding={isEmbedding}
              config={{
                provider: config.fallback.provider,
                model: config.fallback.model,
                fallback: null,
              }}
              onChange={(fb) =>
                onChange({
                  ...config,
                  fallback: { provider: fb.provider, model: fb.model },
                })
              }
              authProfiles={authProfiles}
            />
          </div>
        )}
      </div>
    </Card>
  );
}

export function SettingsModels() {
  const [providers, setProviders] = useState<ProvidersMap>({});
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [authProfiles, setAuthProfiles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reindexNotice, setReindexNotice] = useState<{
    configured: string;
    active: string | null;
    count: number;
  } | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/settings/providers").then((r) => r.json()),
      fetch("/api/settings/models").then((r) => r.json()),
      fetch("/api/settings/auth").then((r) => r.json()),
    ])
      .then(([provs, cfg, profiles]) => {
        setProviders(provs);
        setConfig(cfg);
        const profileProviders = new Set<string>(
          (profiles as { provider: string }[]).map((p) => p.provider)
        );
        setAuthProfiles(profileProviders);
      })
      .catch(() => setError("Failed to load model settings."))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setSaved(false);
    try {
      const res = await fetch("/api/settings/models", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        try {
          const statusRes = await fetch("/api/ai/embedding/status");
          if (statusRes.ok) {
            const status = await statusRes.json();
            if (status.configured_signature !== status.active_signature) {
              setReindexNotice({
                configured: status.configured_signature,
                active: status.active_signature,
                count: status.resumes.length,
              });
            } else {
              setReindexNotice(null);
            }
          }
        } catch {
          // ignore; the resumes-page banner will still surface any mismatch
        }
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading || !config) {
    return <p className="text-sm text-muted-foreground">{error ?? "Loading..."}</p>;
  }

  return (
    <form onSubmit={handleSave} className="space-y-6 max-w-2xl">
      {(["default", "classifier", "embedding", "interview"] as const).map((role) => (
        <RoleCard
          key={role}
          role={role}
          providers={providers}
          config={config[role]}
          onChange={(updated) => setConfig({ ...config, [role]: updated })}
          authProfiles={authProfiles}
        />
      ))}

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
        {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
      </div>

      {reindexNotice && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Embedding model changed to <code>{reindexNotice.configured}</code>.{" "}
          {reindexNotice.count} resumes need reindexing.{" "}
          <a href="/resumes" className="font-medium underline">
            Go to Resume tab →
          </a>
        </div>
      )}
    </form>
  );
}
