"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, BarChart3, FileText, Settings } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  {
    href: "/applications",
    icon: ClipboardList,
    label: "Applications",
  },
  {
    href: "/analytics",
    icon: BarChart3,
    label: "Analytics & Goals",
  },
  {
    href: "/resumes",
    icon: FileText,
    label: "Resumes",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <TooltipProvider>
      <aside className="flex h-screen w-14 flex-col items-center border-r bg-background py-4">
        <Link
          href="/applications"
          className="mb-6 text-sm font-bold text-primary"
        >
          JT
        </Link>

        <nav className="flex flex-1 flex-col items-center gap-2">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger
                  render={
                    <Link
                      href={item.href}
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                        isActive
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    />
                  }
                >
                  <item.icon className="h-5 w-5" />
                </TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>

        <div className="flex flex-col items-center gap-2">
          <Tooltip>
            <TooltipTrigger
              render={
                <Link
                  href="/settings"
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                    pathname.startsWith("/settings")
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                />
              }
            >
              <Settings className="h-5 w-5" />
            </TooltipTrigger>
            <TooltipContent side="right">Settings</TooltipContent>
          </Tooltip>
          <ThemeToggle />
        </div>
      </aside>
    </TooltipProvider>
  );
}
