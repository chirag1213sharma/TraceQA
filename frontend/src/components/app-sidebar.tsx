"use client";

import {
  BrainCircuit,
  ChartNoAxesCombined,
  ChevronsUpDown,
  GitCommitHorizontal,
  Settings2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

const navigation = [
  {
    label: "Dashboard",
    href: "/",
    icon: ChartNoAxesCombined,
  },
  {
    label: "AI Insights",
    href: "/insights",
    icon: BrainCircuit,
  },
  {
    label: "Commit Radar",
    href: "/commits",
    icon: GitCommitHorizontal,
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings2,
  },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { setOpenMobile } = useSidebar();

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader className="p-3">
        <Link
          href="/"
          onClick={() => setOpenMobile(false)}
          className="flex h-11 items-center gap-3 rounded-lg px-2 transition-colors hover:bg-sidebar-accent"
        >
          <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/25">
            <Sparkles className="size-4" aria-hidden="true" />
          </span>
          <span className="grid min-w-0 flex-1 text-left leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-semibold tracking-tight">
              TraceQA
            </span>
            <span className="truncate text-[11px] text-muted-foreground">
              Quality intelligence
            </span>
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navigation.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);

                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      render={
                        <Link
                          href={item.href}
                          onClick={() => setOpenMobile(false)}
                        />
                      }
                      isActive={isActive}
                      tooltip={item.label}
                      size="lg"
                      className="font-medium"
                    >
                      <item.icon className="size-4" aria-hidden="true" />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="Local workspace"
              className="data-[state=open]:bg-sidebar-accent"
            >
              <span className="flex size-8 items-center justify-center rounded-lg border bg-background font-mono text-[10px] font-semibold text-primary">
                LCL
              </span>
              <span className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">Local workspace</span>
                <span className="truncate text-xs text-muted-foreground">
                  Development
                </span>
              </span>
              <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
