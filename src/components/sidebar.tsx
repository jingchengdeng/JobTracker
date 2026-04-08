"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardList, BarChart3, FileText, Settings, Briefcase } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/applications", icon: ClipboardList, label: "Applications" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/resumes", icon: FileText, label: "Resumes" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-14 md:w-56 flex-col border-r border-white/[0.06] bg-white/[0.03] dark:bg-white/[0.03] backdrop-blur-xl">
      <div className="flex h-14 items-center gap-2.5 justify-center md:justify-start px-2 md:px-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-400 text-white shadow-sm shadow-indigo-500/25">
          <Briefcase className="h-4 w-4" />
        </div>
        <span className="hidden md:inline text-base font-semibold tracking-tight">JobTracker</span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2 md:px-3 pt-2">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              className={cn(
                "flex items-center gap-3 rounded-lg px-0 md:px-3 py-2 text-sm font-medium transition-colors justify-center md:justify-start",
                isActive
                  ? "bg-indigo-500/20 text-indigo-300 dark:text-indigo-300 text-indigo-700"
                  : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground"
              )}
            >
              <item.icon className="h-[18px] w-[18px] shrink-0" />
              <span className="hidden md:inline">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-col gap-1 border-t border-white/[0.06] px-2 md:px-3 py-3">
        <Link
          href="/settings"
          title="Settings"
          className={cn(
            "flex items-center gap-3 rounded-lg px-0 md:px-3 py-2 text-sm font-medium transition-colors justify-center md:justify-start",
            pathname.startsWith("/settings")
              ? "bg-indigo-500/20 text-indigo-300 dark:text-indigo-300 text-indigo-700"
              : "text-muted-foreground hover:bg-white/[0.05] hover:text-foreground"
          )}
        >
          <Settings className="h-[18px] w-[18px] shrink-0" />
          <span className="hidden md:inline">Settings</span>
        </Link>
        <div className="flex items-center gap-3 px-0 md:px-3 py-1 justify-center md:justify-start">
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
