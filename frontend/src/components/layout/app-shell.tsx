"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ConnectionStatus } from "@/components/layout/connection-status";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { useLiveUpdates } from "@/lib/ws";

const NAV = [
  { href: "/", label: "סקירה כללית" },
  { href: "/positions", label: "פוזיציות" },
  { href: "/trades", label: "עסקאות" },
  { href: "/journal", label: "יומן מסחר" },
  { href: "/performance", label: "ביצועים" },
  { href: "/risk", label: "סיכונים" },
  { href: "/insights", label: "תובנות" },
  { href: "/sync", label: "סנכרון" },
  { href: "/reports", label: "דוחות" },
  { href: "/settings", label: "הגדרות" },
  { href: "/system", label: "מצב מערכת" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useLiveUpdates();

  return (
    <div className="flex min-h-dvh">
      <aside className="w-52 shrink-0 border-e border-line bg-panel">
        <div className="flex h-12 items-center gap-2 border-b border-line px-4">
          <span className="text-[15px] font-semibold tracking-tight">תיק השקעות</span>
          <span className="sym text-[10px] font-medium text-faint">IBKR</span>
        </div>
        <nav className="flex flex-col gap-0.5 p-2" aria-label="ניווט ראשי">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`nav-item rounded-sm px-3 py-1.5 text-[13px] transition-colors ${
                  active
                    ? "nav-item--active bg-subtle font-medium text-fg"
                    : "text-muted hover:bg-hover hover:text-fg"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center justify-between border-b border-line bg-panel px-4">
          <ConnectionStatus />
          <ThemeToggle />
        </header>
        <main className="min-w-0 flex-1 p-5">{children}</main>
      </div>
    </div>
  );
}
