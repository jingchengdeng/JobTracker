"use client";

import { Copy, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { LinkedinContact } from "@/lib/types";

interface LinkedinContactCardProps {
  contact: LinkedinContact;
}

function scoreColor(score: number): string {
  if (score >= 70) return "bg-green-500/10 text-green-600 dark:text-green-400";
  if (score >= 40) return "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400";
  return "bg-red-500/10 text-red-600 dark:text-red-400";
}

export function LinkedinContactCard({ contact }: LinkedinContactCardProps) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium truncate">{contact.name}</p>
            <a
              href={contact.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0"
            >
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
            </a>
          </div>
          <p className="text-sm text-muted-foreground truncate">{contact.title}</p>
          {contact.location && (
            <p className="text-xs text-muted-foreground">{contact.location}</p>
          )}
        </div>
        <Badge variant="secondary" className={scoreColor(contact.relevance_score)}>
          {contact.relevance_score}
        </Badge>
      </div>

      <div className="rounded bg-muted p-3 text-sm">
        <p>{contact.connection_note}</p>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {contact.connection_note.length}/300
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => navigator.clipboard.writeText(contact.connection_note)}
          >
            <Copy className="mr-1.5 h-3.5 w-3.5" />
            Copy
          </Button>
        </div>
      </div>
    </Card>
  );
}
