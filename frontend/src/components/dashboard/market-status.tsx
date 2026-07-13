"use client";

/*
  MarketStatus — the Legend "Market hours" pill. Computes US regular-session
  state (Mon–Fri 09:30–16:00 America/New_York) on the client only, so there is
  no SSR/hydration mismatch. A live green dot while open; a muted dot otherwise.
  This is a presentation aid over wall-clock time, not a trading-calendar feed —
  it does not know about market holidays.
*/

import { useEffect, useState } from "react";

type Phase = "open" | "pre" | "after" | "closed";

function nyParts(now: Date) {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = fmt.formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const weekday = get("weekday");
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  return { weekday, minutes: hour * 60 + minute };
}

function phaseOf(now: Date): Phase {
  const { weekday, minutes } = nyParts(now);
  const weekend = weekday === "Sat" || weekday === "Sun";
  if (weekend) return "closed";
  const open = 9 * 60 + 30;
  const close = 16 * 60;
  if (minutes >= open && minutes < close) return "open";
  if (minutes >= 4 * 60 && minutes < open) return "pre";
  if (minutes >= close && minutes < 20 * 60) return "after";
  return "closed";
}

const LABEL: Record<Phase, string> = {
  open: "שעות מסחר",
  pre: "טרום־מסחר",
  after: "אחרי הנעילה",
  closed: "השוק סגור",
};

export function MarketStatus() {
  const [phase, setPhase] = useState<Phase | null>(null);
  useEffect(() => {
    const tick = () => setPhase(phaseOf(new Date()));
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const open = phase === "open";
  return (
    <span className="chip" dir="rtl">
      <span
        aria-hidden
        className={`size-1.5 rounded-full ${open ? "bg-gain live-dot" : "bg-faint"}`}
        style={open ? { boxShadow: "0 0 8px var(--glow)" } : undefined}
      />
      <span className={open ? "text-fg" : "text-muted"}>{phase ? LABEL[phase] : LABEL.closed}</span>
    </span>
  );
}
