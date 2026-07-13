"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ConnectionStatus } from "@/components/layout/connection-status";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NavIcon, type IconName } from "@/components/layout/nav-icons";
import { Clock } from "@/components/layout/clock";
import { MarketStatus } from "@/components/dashboard/market-status";
import { fetchConnection } from "@/lib/api";
import { useLiveUpdates } from "@/lib/ws";

type NavItem = { href: string; label: string; icon: IconName; warn?: boolean };
type NavGroup = { label: string; items: NavItem[] };

const NAV: NavGroup[] = [
  {
    label: "ליבה",
    items: [
      { href: "/", label: "סקירה כללית", icon: "grid" },
      { href: "/positions", label: "פוזיציות", icon: "layers" },
      { href: "/trades", label: "עסקאות", icon: "swap" },
    ],
  },
  {
    label: "אנליטיקה",
    items: [
      { href: "/journal", label: "יומן מסחר", icon: "book" },
      { href: "/performance", label: "ביצועים", icon: "chart" },
      { href: "/risk", label: "סיכונים", icon: "shield" },
      { href: "/insights", label: "תובנות", icon: "bulb" },
    ],
  },
  {
    label: "מידע",
    items: [
      { href: "/news", label: "חדשות", icon: "news" },
      { href: "/reports", label: "דוחות", icon: "file" },
    ],
  },
  {
    label: "מערכת",
    items: [
      { href: "/sync", label: "סנכרון", icon: "refresh" },
      { href: "/settings", label: "הגדרות", icon: "sliders" },
      { href: "/system", label: "מצב מערכת", icon: "pulse" },
    ],
  },
];

const FLAT = NAV.flatMap((g) => g.items);

function maskAccount(acct: string | null | undefined): string {
  if (!acct) return "IBKR";
  const last4 = acct.slice(-4);
  return `U-•••${last4}`;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useLiveUpdates();
  const { data: conn } = useQuery({
    queryKey: ["connection"],
    queryFn: fetchConnection,
    refetchInterval: 5_000,
  });

  const current = FLAT.find((i) =>
    i.href === "/" ? pathname === "/" : pathname.startsWith(i.href),
  );
  const title = current?.label ?? "תיק השקעות";

  return (
    <div className="grid min-h-dvh grid-cols-[230px_1fr]">
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className="sticky top-0 flex h-dvh flex-col border-e border-line bg-[var(--bg-panel)]">
        <div className="flex items-center gap-3 border-b border-line px-4 py-3.5">
          <span className="grid size-[30px] place-items-center rounded-lg border border-[color-mix(in_srgb,var(--accent)_30%,var(--border))] bg-gradient-to-b from-[#0b2a1d] to-[#0a0f0d]">
            <span
              className="size-[11px] rounded-[3px] bg-accent"
              style={{ boxShadow: "0 0 10px var(--glow)" }}
            />
          </span>
          <div className="min-w-0">
            <div className="text-[13px] font-semibold tracking-tight">תיק השקעות</div>
            <div className="sym text-[9.5px] tracking-[0.18em] text-faint">IBKR · WEALTH</div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-3" aria-label="ניווט ראשי">
          {NAV.map((group) => (
            <div key={group.label} className="mb-1">
              <div className="px-2.5 pb-1.5 pt-3 text-[9.5px] font-medium tracking-[0.16em] text-faint">
                {group.label}
              </div>
              {group.items.map((item) => {
                const active =
                  item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`nav-item press flex items-center gap-3 rounded-lg px-2.5 py-[7px] text-[12.5px] font-medium ${
                      active
                        ? "nav-item--active bg-[linear-gradient(90deg,var(--accent-soft),transparent)] text-[color-mix(in_srgb,var(--accent)_45%,var(--fg))]"
                        : "text-muted hover:bg-hover hover:text-fg"
                    }`}
                  >
                    <NavIcon
                      name={item.icon}
                      className={active ? "text-accent" : "text-faint"}
                    />
                    <span className="truncate">{item.label}</span>
                    {item.warn && (
                      <span
                        aria-hidden
                        className="ms-auto size-1.5 rounded-full bg-warn"
                        style={{ boxShadow: "0 0 7px color-mix(in srgb, var(--warn) 60%, transparent)" }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="flex items-center gap-2 border-t border-line px-4 py-3 text-[11px] text-faint">
          <span
            aria-hidden
            className="size-1.5 rounded-full bg-gain live-dot"
            style={{ boxShadow: "0 0 8px var(--glow)" }}
          />
          <span>IBKR Web API</span>
          <span className="ms-auto">קריאה בלבד</span>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-col">
        <header className="widget-head flex items-center gap-3 border-b border-line px-6 py-2.5">
          <div className="min-w-0">
            <div className="text-[15px] font-semibold leading-tight">{title}</div>
            <div className="text-[11px] text-faint">
              חשבון מרג'ין · <span className="sym">{maskAccount(conn?.account)}</span>
            </div>
          </div>
          <div className="ms-auto flex items-center gap-2.5">
            <MarketStatus />
            <ConnectionStatus />
            <span className="chip">
              <span className="text-faint">עודכן</span>
              <Clock />
            </span>
            <span className="chip">
              <span className="text-faint">מטבע</span>
              <span className="sym">USD</span>
            </span>
            <ThemeToggle />
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4">{children}</main>
      </div>
    </div>
  );
}
