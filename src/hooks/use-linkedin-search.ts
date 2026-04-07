"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import type { LinkedinSearchResult, LinkedinSearch, LinkedinCompany, LinkedinContact } from "@/lib/types";

export function useLinkedInSearch(jobId: number) {
  const [search, setSearch] = useState<LinkedinSearch | null>(null);
  const [company, setCompany] = useState<LinkedinCompany | null>(null);
  const [contacts, setContacts] = useState<LinkedinContact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Load existing search on mount
  useEffect(() => {
    async function loadExisting() {
      const res = await fetch(`/api/ai/linkedin/job/${jobId}`);
      if (res.ok) {
        const data: LinkedinSearchResult = await res.json();
        if (data.search) {
          setSearch(data.search);
          setCompany(data.company);
          setContacts(data.contacts);
        }
      }
    }
    loadExisting();
  }, [jobId]);

  const startSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetch("/api/ai/linkedin/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    if (!res.ok) {
      setError("Failed to start search");
      setLoading(false);
      return;
    }
    const data = await res.json();
    const searchId = data.search_id;
    setSearch({ id: searchId, status: "running", started_at: new Date().toISOString(), completed_at: null });
    setCompany(null);
    setContacts([]);

    // Poll for completion
    if (pollRef.current) clearInterval(pollRef.current);
    let elapsed = 0;
    const poll = setInterval(async () => {
      elapsed += 1500;
      if (elapsed > 180000) {
        clearInterval(poll);
        pollRef.current = null;
        setLoading(false);
        setError("Search timed out");
        return;
      }
      const pollRes = await fetch(`/api/ai/linkedin/${searchId}`);
      if (pollRes.ok) {
        const pollData: LinkedinSearchResult = await pollRes.json();
        if (pollData.search?.status === "completed") {
          clearInterval(poll);
          pollRef.current = null;
          setSearch(pollData.search);
          setCompany(pollData.company);
          setContacts(pollData.contacts);
          setLoading(false);
        } else if (pollData.search?.status === "failed") {
          clearInterval(poll);
          pollRef.current = null;
          setSearch(pollData.search);
          setLoading(false);
          setError("Search failed");
        }
      }
    }, 1500);
    pollRef.current = poll;
  }, [jobId]);

  const deleteSearch = useCallback(async () => {
    if (!search) return;
    await fetch(`/api/ai/linkedin/${search.id}`, { method: "DELETE" });
    setSearch(null);
    setCompany(null);
    setContacts([]);
    setError(null);
  }, [search]);

  return {
    search,
    company,
    contacts,
    loading,
    error,
    startSearch,
    deleteSearch,
  };
}
