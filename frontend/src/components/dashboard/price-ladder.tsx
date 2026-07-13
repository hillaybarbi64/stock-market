"use client";

/*
  PriceLadder — the right-rail panel that reads like the Legend order-book DOM,
  but built from data we actually have (read-only, no live book): a volume-by-
  price profile over the recent bars. Each row is a price level; the horizontal
  bar is how much volume traded there. The current price row is highlighted and
  the average-cost level is tagged, so the ladder shows, at a glance, whether
  price is sitting above or below your basis and where the volume shelf is.
  Renders LTR (price ladder reads top=high → bottom=low).
*/

import { useMemo } from "react";
import type { Bar } from "@/components/charts/candlestick-chart";
import { Num } from "@/components/ui/num";

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

interface Level {
  price: number;
  vol: number; // 0..1 of the busiest level
  current: boolean;
  cost: boolean;
}

export function PriceLadder({
  bars,
  last,
  avgCost,
  levels = 15,
}: {
  bars: Bar[];
  last: number | null;
  avgCost: number | null;
  levels?: number;
}) {
  const model = useMemo(() => {
    const window = bars.slice(-70);
    if (window.length < 2) return null;
    const hi = Math.max(...window.map((b) => b.high));
    const lo = Math.min(...window.map((b) => b.low));
    const span = hi - lo || 1;
    const step = span / levels;
    const buckets = new Array<number>(levels).fill(0);
    // Spread each bar's volume across the levels its [low, high] range spans.
    for (const b of window) {
      const loIdx = clamp(Math.floor((b.low - lo) / step), 0, levels - 1);
      const hiIdx = clamp(Math.floor((b.high - lo) / step), 0, levels - 1);
      const n = hiIdx - loIdx + 1;
      for (let i = loIdx; i <= hiIdx; i++) buckets[i] += b.volume / n;
    }
    const maxVol = Math.max(...buckets, 1);
    const curIdx = last != null ? clamp(Math.floor((last - lo) / step), 0, levels - 1) : -1;
    const costIdx = avgCost != null ? clamp(Math.floor((avgCost - lo) / step), 0, levels - 1) : -1;
    const rows: Level[] = [];
    for (let i = levels - 1; i >= 0; i--) {
      rows.push({
        price: lo + step * (i + 0.5),
        vol: buckets[i] / maxVol,
        current: i === curIdx,
        cost: i === costIdx,
      });
    }
    return { rows, hi, lo };
  }, [bars, last, avgCost, levels]);

  if (!model) {
    return (
      <p className="px-3.5 py-8 text-center text-[12px] text-muted">
        סולם מחיר יופיע לאחר סנכרון היסטוריית מחירים.
      </p>
    );
  }

  return (
    <div dir="ltr" className="select-none">
      {model.rows.map((row, i) => {
        const aboveCost = avgCost != null && row.price >= avgCost;
        return (
          <div
            key={i}
            className={`relative flex items-center justify-between px-3 py-[3px] text-[11px] ${
              row.current ? "bg-accent-soft" : ""
            }`}
          >
            {/* volume-by-price bar, grows from the price toward the left */}
            <span
              aria-hidden
              className="absolute inset-y-[2px] right-[64px] rounded-s-[2px]"
              style={{
                width: `calc(${(row.vol * 100).toFixed(1)}% * 0.72)`,
                background: aboveCost
                  ? "color-mix(in srgb, var(--gain) 20%, transparent)"
                  : "color-mix(in srgb, var(--loss) 18%, transparent)",
              }}
            />
            <span className="relative z-10 flex items-center gap-1.5">
              {row.cost && (
                <span
                  className="rounded-[3px] border border-[color-mix(in_srgb,var(--warn)_45%,transparent)] px-1 py-px text-[8.5px] font-semibold tracking-wide text-warn"
                  title="מחיר עלות ממוצע"
                >
                  AVG
                </span>
              )}
              {row.current && (
                <span
                  aria-hidden
                  className="size-1.5 rounded-full bg-accent"
                  style={{ boxShadow: "0 0 6px var(--glow)" }}
                />
              )}
            </span>
            <span
              className={`relative z-10 w-[60px] text-end tabular-nums ${
                row.current ? "font-semibold text-fg" : "text-muted"
              }`}
            >
              <Num value={row.price} kind="price" />
            </span>
          </div>
        );
      })}
    </div>
  );
}
