"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Preference {
  id: number;
  content: string;
  createdAt: string;
}

export function SettingsPreferences() {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [loading, setLoading] = useState(true);
  const [newContent, setNewContent] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  async function load() {
    try {
      const res = await fetch("/api/settings/preferences");
      if (res.ok) {
        setPreferences(await res.json());
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
    if (!newContent.trim()) return;
    setAdding(true);
    try {
      const res = await fetch("/api/settings/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: newContent.trim() }),
      });
      if (res.ok) {
        setNewContent("");
        load();
      }
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: number) {
    const res = await fetch(`/api/settings/preferences/${id}`, {
      method: "DELETE",
    });
    if (res.ok) {
      setPreferences((prev) => prev.filter((p) => p.id !== id));
    }
  }

  function startEdit(pref: Preference) {
    setEditingId(pref.id);
    setEditValue(pref.content);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditValue("");
  }

  async function confirmEdit(id: number) {
    if (!editValue.trim()) return;
    const res = await fetch(`/api/settings/preferences/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: editValue.trim() }),
    });
    if (res.ok) {
      setEditingId(null);
      setEditValue("");
      load();
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <form onSubmit={handleAdd} className="flex gap-2">
        <Input
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          placeholder="Add a preference, e.g. remote only, no startups..."
          className="flex-1"
        />
        <Button type="submit" size="sm" disabled={adding || !newContent.trim()}>
          <Plus />
          Add
        </Button>
      </form>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : preferences.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No preferences yet. Add some to help the AI tailor recommendations.
        </p>
      ) : (
        <ul className="divide-y divide-white/[0.06] rounded-lg border border-white/[0.06]">
          {preferences.map((pref) => (
            <li key={pref.id} className="flex items-center gap-2 px-3 py-2.5">
              {editingId === pref.id ? (
                <>
                  <Input
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="flex-1 h-7 text-sm"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmEdit(pref.id);
                      if (e.key === "Escape") cancelEdit();
                    }}
                  />
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={() => confirmEdit(pref.id)}
                    aria-label="Save"
                  >
                    <Check />
                  </Button>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={cancelEdit}
                    aria-label="Cancel"
                  >
                    <X />
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-sm">{pref.content}</span>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={() => startEdit(pref)}
                    aria-label="Edit"
                  >
                    <Pencil />
                  </Button>
                  <Button
                    size="icon-xs"
                    variant="ghost"
                    onClick={() => handleDelete(pref.id)}
                    aria-label="Delete"
                  >
                    <Trash2 />
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
