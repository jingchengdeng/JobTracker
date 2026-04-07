"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { LinkedinCompany } from "@/lib/types";

interface LinkedinCompanyCardProps {
  company: LinkedinCompany;
}

function CollapsibleSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t pt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        {title}
      </button>
      {open && <div className="mt-2 text-sm">{children}</div>}
    </div>
  );
}

export function LinkedinCompanyCard({ company }: LinkedinCompanyCardProps) {
  const d = company.data;
  const name = (d.name as string) || "Unknown";
  const industry = (d.industry as string) || null;
  const employees = d.estimated_num_employees as number | null;
  const founded = d.founded_year as number | null;
  const revenue = d.annual_revenue_printed as string | null;
  const funding = d.total_funding_printed as string | null;
  const latestRound = d.latest_funding_stage as string | null;
  const hq = [d.city, d.state, d.country].filter(Boolean).join(", ");
  const shortDesc = d.short_description as string | null;
  const logoUrl = d.logo_url as string | null;
  const linkedinUrl = d.linkedin_url as string | null;
  const deptHeadcount = d.departmental_head_count as Record<string, number> | null;
  const techNames = (d.technology_names as string[]) || [];
  const fundingEvents = (d.funding_events as Array<Record<string, unknown>>) || [];
  const subOrgs = (d.suborganizations as Array<Record<string, unknown>>) || [];
  const keywords = (d.keywords as string[]) || [];

  return (
    <Card className="p-4 space-y-3">
      {company.summary && (
        <p className="text-sm text-muted-foreground italic">{company.summary}</p>
      )}

      <div className="flex items-center gap-3">
        {logoUrl ? (
          <img src={logoUrl} alt={name} className="h-12 w-12 rounded-lg object-contain" />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-lg font-bold">
            {name.charAt(0)}
          </div>
        )}
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-medium">{name}</h3>
            {linkedinUrl && (
              <a href={linkedinUrl} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
              </a>
            )}
          </div>
          {industry && <p className="text-sm text-muted-foreground capitalize">{industry}</p>}
        </div>
      </div>

      {shortDesc && <p className="text-sm">{shortDesc}</p>}

      <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {employees && (
          <div>
            <p className="font-medium">{employees.toLocaleString()}</p>
            <p className="text-muted-foreground">Employees</p>
          </div>
        )}
        {founded && (
          <div>
            <p className="font-medium">{founded}</p>
            <p className="text-muted-foreground">Founded</p>
          </div>
        )}
        {revenue && (
          <div>
            <p className="font-medium">{revenue}</p>
            <p className="text-muted-foreground">Revenue</p>
          </div>
        )}
        {funding && (
          <div>
            <p className="font-medium">{funding}{latestRound ? ` (${latestRound})` : ""}</p>
            <p className="text-muted-foreground">Total Funding</p>
          </div>
        )}
      </div>

      {hq && <p className="text-sm text-muted-foreground">HQ: {hq}</p>}

      {deptHeadcount && Object.keys(deptHeadcount).length > 0 && (
        <CollapsibleSection title="Department Breakdown">
          <div className="grid grid-cols-2 gap-1">
            {Object.entries(deptHeadcount)
              .sort(([, a], [, b]) => b - a)
              .map(([dept, count]) => (
                <div key={dept} className="flex justify-between rounded px-2 py-0.5 odd:bg-muted/50">
                  <span className="capitalize">{dept.replace(/_/g, " ")}</span>
                  <span className="font-medium">{count.toLocaleString()}</span>
                </div>
              ))}
          </div>
        </CollapsibleSection>
      )}

      {techNames.length > 0 && (
        <CollapsibleSection title={`Tech Stack (${techNames.length})`}>
          <div className="flex flex-wrap gap-1">
            {techNames.slice(0, 50).map((tech) => (
              <span key={tech} className="rounded bg-muted px-1.5 py-0.5 text-xs">{tech}</span>
            ))}
            {techNames.length > 50 && (
              <span className="text-xs text-muted-foreground">+{techNames.length - 50} more</span>
            )}
          </div>
        </CollapsibleSection>
      )}

      {fundingEvents.length > 0 && (
        <CollapsibleSection title={`Funding History (${fundingEvents.length} rounds)`}>
          <div className="space-y-1">
            {fundingEvents.slice(0, 10).map((event, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span>{(event.type as string) || "Round"}</span>
                <span className="text-muted-foreground">{(event.date as string)?.slice(0, 10) || ""}</span>
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {subOrgs.length > 0 && (
        <CollapsibleSection title={`Subsidiaries (${subOrgs.length})`}>
          <div className="space-y-0.5">
            {subOrgs.map((org, i) => (
              <p key={i} className="text-xs">{org.name as string}</p>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {keywords.length > 0 && (
        <CollapsibleSection title="Keywords">
          <div className="flex flex-wrap gap-1">
            {keywords.slice(0, 30).map((kw) => (
              <span key={kw} className="rounded bg-muted px-1.5 py-0.5 text-xs">{kw}</span>
            ))}
          </div>
        </CollapsibleSection>
      )}
    </Card>
  );
}
