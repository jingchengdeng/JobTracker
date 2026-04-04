"use client";

import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Job } from "@/lib/types";

interface LinkedinTabProps {
  job: Job;
}

const MOCK_CONNECTIONS = [
  {
    name: "Sarah Chen",
    title: "Senior Software Engineer",
    degree: "2nd",
    note: "Hi Sarah, I noticed you're at {company} and I'm very interested in the {title} role. I'd love to learn more about the team culture and engineering challenges you're tackling. Would you be open to a brief chat?",
  },
  {
    name: "Marcus Johnson",
    title: "Engineering Manager",
    degree: "2nd",
    note: "Hi Marcus, I came across the {title} opening at {company} and your leadership of the backend team caught my eye. I have experience in similar domains and would appreciate any insights about what the team is looking for.",
  },
  {
    name: "Priya Patel",
    title: "Technical Recruiter",
    degree: "3rd",
    note: "Hi Priya, I'm applying for the {title} position at {company} and wanted to connect. I believe my background aligns well with what you're looking for. Happy to share more details if helpful!",
  },
];

export function LinkedinTab({ job }: LinkedinTabProps) {
  function fillTemplate(text: string) {
    return text
      .replace("{company}", job.company)
      .replace("{title}", job.title);
  }

  return (
    <div className="space-y-4">
      <Badge variant="secondary" className="bg-amber-500/10 text-amber-600 dark:text-amber-400">
        Demo -- mock data for preview
      </Badge>

      <Card className="p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-lg font-bold">
            {job.company.charAt(0)}
          </div>
          <div>
            <h3 className="font-medium">{job.company}</h3>
            <p className="text-sm text-muted-foreground">Technology company</p>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4 text-center text-sm">
          <div>
            <p className="font-medium">5,000+</p>
            <p className="text-muted-foreground">Employees</p>
          </div>
          <div>
            <p className="font-medium">2015</p>
            <p className="text-muted-foreground">Founded</p>
          </div>
          <div>
            <p className="font-medium">Series D</p>
            <p className="text-muted-foreground">Funding</p>
          </div>
          <div>
            <p className="font-medium">San Francisco</p>
            <p className="text-muted-foreground">HQ</p>
          </div>
        </div>
      </Card>

      <h3 className="font-medium">Suggested Connections</h3>
      {MOCK_CONNECTIONS.map((conn, i) => {
        const note = fillTemplate(conn.note);
        return (
          <Card key={i} className="p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-medium">{conn.name}</p>
                <p className="text-sm text-muted-foreground">{conn.title}</p>
              </div>
              <Badge variant="secondary">{conn.degree}</Badge>
            </div>
            <div className="rounded bg-muted p-3 text-sm">
              <p>{note}</p>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {note.length}/300
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigator.clipboard.writeText(note)}
                >
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  Copy
                </Button>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
