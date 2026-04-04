"use client";

import { useState, useEffect } from "react";
import { Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";

interface AuthProfile {
  id: string;
  type: "api_key" | "oauth";
  provider: string;
  maskedKey?: string;
  status: "active" | "connected" | "expired";
}

export function SettingsApiKeys() {
  const [profiles, setProfiles] = useState<AuthProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [provider, setProvider] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const res = await fetch("/api/settings/auth");
      if (res.ok) {
        setProfiles(await res.json());
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!provider.trim() || !apiKey.trim()) return;
    setSaving(true);
    try {
      const res = await fetch("/api/settings/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: provider.trim(), key: apiKey.trim() }),
      });
      if (res.ok) {
        setAddOpen(false);
        setProvider("");
        setApiKey("");
        load();
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    const res = await fetch("/api/settings/auth", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (res.ok) {
      load();
    }
  }

  const oauthProfiles = profiles.filter((p) => p.type === "oauth");
  const apiKeyProfiles = profiles.filter((p) => p.type === "api_key");

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  return (
    <div className="space-y-8 max-w-xl">
      {/* OAuth section */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold">Subscription Logins</h2>
        {oauthProfiles.length === 0 ? (
          <p className="text-sm text-muted-foreground">No OAuth accounts connected.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {oauthProfiles.map((profile) => (
              <li key={profile.id} className="flex items-center justify-between px-3 py-2.5">
                <span className="text-sm font-medium capitalize">{profile.provider}</span>
                <div className="flex items-center gap-2">
                  <Badge variant={profile.status === "expired" ? "destructive" : "secondary"}>
                    {profile.status === "expired" ? "Expired" : "Connected"}
                  </Badge>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={() => handleDelete(profile.id)}
                    aria-label={`Remove ${profile.provider}`}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* API Keys section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">API Keys</h2>
          <Dialog open={addOpen} onOpenChange={setAddOpen}>
            <DialogTrigger render={<Button size="sm" variant="outline" />}>
              <Plus />
              Add Key
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add API Key</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleAdd} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="api-provider">Provider</Label>
                  <Input
                    id="api-provider"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    placeholder="e.g. openai"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="api-key">Key</Label>
                  <Input
                    id="api-key"
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    required
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <DialogClose render={<Button type="button" variant="outline" />}>
                    Cancel
                  </DialogClose>
                  <Button type="submit" disabled={saving || !provider.trim() || !apiKey.trim()}>
                    {saving ? "Saving..." : "Save"}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {apiKeyProfiles.length === 0 ? (
          <p className="text-sm text-muted-foreground">No API keys saved yet.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {apiKeyProfiles.map((profile) => (
              <li key={profile.id} className="flex items-center justify-between px-3 py-2.5">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium capitalize">{profile.provider}</p>
                  {profile.maskedKey && (
                    <p className="font-mono text-xs text-muted-foreground">{profile.maskedKey}</p>
                  )}
                </div>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  onClick={() => handleDelete(profile.id)}
                  aria-label={`Remove ${profile.provider} key`}
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        Keys are stored locally on this machine and are never sent to external servers.
      </p>
    </div>
  );
}
