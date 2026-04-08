"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { SettingsApiKeys } from "@/components/settings-api-keys";
import { SettingsModels } from "@/components/settings-models";
import { SettingsPreferences } from "@/components/settings-preferences";

const tabs = [
  { id: "api-keys", label: "API Keys" },
  { id: "model", label: "Model" },
  { id: "preferences", label: "Preferences" },
] as const;

type TabId = (typeof tabs)[number]["id"];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("api-keys");

  return (
    <div className="space-y-6 px-8 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure API keys, models, and preferences
        </p>
      </div>

      <div className="flex gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors cursor-pointer",
              activeTab === tab.id
                ? "bg-indigo-500/15 text-indigo-300 dark:text-indigo-300 text-indigo-700"
                : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="pt-2">
        {activeTab === "api-keys" && <SettingsApiKeys />}
        {activeTab === "model" && <SettingsModels />}
        {activeTab === "preferences" && <SettingsPreferences />}
      </div>
    </div>
  );
}
