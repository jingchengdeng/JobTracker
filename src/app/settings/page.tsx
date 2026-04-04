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
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <div className="flex gap-4 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "pb-2 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "api-keys" && <SettingsApiKeys />}
      {activeTab === "model" && <SettingsModels />}
      {activeTab === "preferences" && <SettingsPreferences />}
    </div>
  );
}
