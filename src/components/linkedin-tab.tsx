"use client";

import { Loader2, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLinkedInSearch } from "@/hooks/use-linkedin-search";
import { LinkedinCompanyCard } from "@/components/linkedin-company-card";
import { LinkedinContactCard } from "@/components/linkedin-contact-card";
import type { Job } from "@/lib/types";

interface LinkedinTabProps {
  job: Job;
}

export function LinkedinTab({ job }: LinkedinTabProps) {
  const { search, company, contacts, loading, error, startSearch, deleteSearch } =
    useLinkedInSearch(job.id);

  // Empty state — no search yet
  if (!search && !loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Search className="mb-3 h-10 w-10 text-muted-foreground" />
        <h3 className="mb-1 font-medium">Find Connections</h3>
        <p className="mb-4 max-w-sm text-sm text-muted-foreground">
          Search for recruiters, hiring managers, and relevant contacts at {job.company} to help with your application.
        </p>
        <Button onClick={startSearch}>
          <Search className="mr-1.5 h-4 w-4" />
          Find Connections
        </Button>
      </div>
    );
  }

  // Running state
  if (search?.status === "running" || loading) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Loader2 className="mb-3 h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Searching for contacts at {job.company}...
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          This usually takes 30-60 seconds.
        </p>
      </div>
    );
  }

  // Error state
  if (search?.status === "failed" || error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="mb-3 text-sm text-destructive">{error || "Search failed"}</p>
        <Button onClick={startSearch} variant="outline">
          <RefreshCw className="mr-1.5 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  // Results state
  const lowConfidence = contacts.some((c) => c.low_confidence === 1);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">Results for {job.company}</h3>
        <Button size="sm" variant="outline" onClick={startSearch} disabled={loading}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {company && <LinkedinCompanyCard company={company} />}

      <h3 className="font-medium">Contacts ({contacts.length})</h3>

      {lowConfidence && (
        <p className="text-xs text-yellow-600 dark:text-yellow-400">
          These are the closest matches we found, but confidence is low.
        </p>
      )}

      {contacts.length === 0 && (
        <p className="text-sm text-muted-foreground">No contacts found.</p>
      )}

      {contacts.map((contact) => (
        <LinkedinContactCard key={contact.id || contact.linkedin_url} contact={contact} />
      ))}
    </div>
  );
}
