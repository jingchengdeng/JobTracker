"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ModelConfig {
  defaultModel: string;
  classifierModel: string;
  embeddingModel: string;
}

const DEFAULTS: ModelConfig = {
  defaultModel: "gpt-4o",
  classifierModel: "gpt-4o-mini",
  embeddingModel: "text-embedding-3-small",
};

export function SettingsModels() {
  const [config, setConfig] = useState<ModelConfig>(DEFAULTS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/settings/models")
      .then((r) => r.json())
      .then((data) => setConfig(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
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
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <form onSubmit={handleSave} className="space-y-6 max-w-xl">
      <div className="space-y-1.5">
        <Label htmlFor="default-model">Default Model</Label>
        <p className="text-xs text-muted-foreground">
          Used for general tasks like drafting cover letters and summarizing job descriptions.
        </p>
        <Input
          id="default-model"
          value={config.defaultModel}
          onChange={(e) => setConfig({ ...config, defaultModel: e.target.value })}
          placeholder={DEFAULTS.defaultModel}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="classifier-model">Classifier Model</Label>
        <p className="text-xs text-muted-foreground">
          Lightweight model used to classify and tag job postings quickly.
        </p>
        <Input
          id="classifier-model"
          value={config.classifierModel}
          onChange={(e) => setConfig({ ...config, classifierModel: e.target.value })}
          placeholder={DEFAULTS.classifierModel}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="embedding-model">Embedding Model</Label>
        <p className="text-xs text-muted-foreground">
          Generates vector embeddings for semantic search across resumes and job postings.
        </p>
        <Input
          id="embedding-model"
          value={config.embeddingModel}
          onChange={(e) => setConfig({ ...config, embeddingModel: e.target.value })}
          placeholder={DEFAULTS.embeddingModel}
        />
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
        {saved && <span className="text-xs text-muted-foreground">Saved.</span>}
      </div>
    </form>
  );
}
