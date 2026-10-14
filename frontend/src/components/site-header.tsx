"use client";

import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

const titles: Record<string, string> = {
  "/": "Dashboard",
  "/insights": "AI Insights",
  "/commits": "Commit Radar",
  "/settings": "Settings",
};

export function SiteHeader() {
  const pathname = usePathname();
  const title = titles[pathname] ?? "TraceQA";

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-xl md:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="h-4!" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold tracking-tight">{title}</p>
      </div>
      <div className="hidden items-center gap-2 sm:flex">
        <span className="size-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_3px] shadow-emerald-500/15" />
        <span className="text-xs text-muted-foreground">Systems operational</span>
      </div>
      <Separator orientation="vertical" className="hidden h-4! sm:block" />
      <ThemeToggle />
    </header>
  );
}
