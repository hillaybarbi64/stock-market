"use client";

import { useMemo, useState } from "react";
import { Sparkline } from "@/components/charts/sparkline";
import { Num, Sym } from "@/components/ui/num";
import type { PositionRow } from "@/lib/types";

type SortKey = "symbol" | "market_value" | "unrealized_pnl" | "daily_pnl" | "weight";

/*
  Positions table (Legend). Each row leads with an asset monogram tile, shows a
  weight depth-bar, and — when a price-history series is supplied — an inline
  sparkline. Row order is stable while prices tick (re-sorted only when the data
  identity or sort choice changes) to avoid jumpy layouts.
*/
export function PositionsTable({
  positions,
  nlv,
  compact = false,
  sparklines,
}: {
  positions: PositionRow[];
  nlv: number | null;
  compact?: boolean;
  /** optional conid → recent closes, for the trend column */
  sparklines?: Record<number, number[]>;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("market_value");
  const [desc, setDesc] = useState(true);

  const rows = useMemo(() => {
    const withWeight = positions.map((p) => ({
      ...p,
      weight:
        nlv && p.market_value != null && nlv !== 0 ? Number(p.market_value) / nlv : null,
    }));
    const dir = desc ? -1 : 1;
    return withWeight.sort((x, y) => {
      if (sortKey === "symbol")
        return dir * x.instrument.symbol.localeCompare(y.instrument.symbol);
      const xv = Number(x[sortKey] ?? Number.NEGATIVE_INFINITY);
      const yv = Number(y[sortKey] ?? Number.NEGATIVE_INFINITY);
      return dir * (xv - yv);
    });
  }, [positions, nlv, sortKey, desc]);

  const hasSpark = !!sparklines && Object.keys(sparklines).length > 0;

  if (positions.length === 0) {
    return (
      <p className="py-6 text-center text-[12.5px] text-muted">אין פוזיציות פתוחות להצגה.</p>
    );
  }

  const th = (key: SortKey, label: string, numeric = true) => (
    <th
      className={`cursor-pointer select-none pb-2 font-normal text-[10.5px] text-faint hover:text-muted ${
        numeric ? "text-end" : "text-start"
      }`}
      onClick={() => {
        if (sortKey === key) setDesc(!desc);
        else {
          setSortKey(key);
          setDesc(true);
        }
      }}
    >
      {label}
      <span
        aria-hidden
        className="ms-0.5 inline-block w-2.5 text-center transition-opacity duration-[120ms]"
        style={{ opacity: sortKey === key ? 1 : 0 }}
      >
        {desc ? "↓" : "↑"}
      </span>
    </th>
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="border-b border-line">
            {th("symbol", "נכס", false)}
            {hasSpark && <th className="pb-2 text-start text-[10.5px] font-normal text-faint">מגמה</th>}
            <th className="pb-2 text-end text-[10.5px] font-normal text-faint">כמות</th>
            <th className="pb-2 text-end text-[10.5px] font-normal text-faint">מחיר ממוצע</th>
            <th className="pb-2 text-end text-[10.5px] font-normal text-faint">מחיר נוכחי</th>
            {th("market_value", "שווי שוק")}
            {th("weight", "משקל בתיק")}
            {th("daily_pnl", "P&L יומי")}
            {th("unrealized_pnl", "P&L לא ממומש")}
            <th className="pb-2 text-end text-[10.5px] font-normal text-faint">מהכניסה %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const entryPct =
              p.avg_cost != null && p.market_price != null && Number(p.avg_cost) !== 0
                ? (Number(p.market_price) - Number(p.avg_cost)) / Number(p.avg_cost)
                : null;
            const weightPct = p.weight != null ? Math.min(Math.max(p.weight, 0), 1) : 0;
            const series = sparklines?.[p.instrument.conid];
            return (
              <tr
                key={p.instrument.conid}
                className="border-b border-line transition-colors duration-[120ms] last:border-0 hover:bg-hover"
              >
                <td className="py-2.5">
                  <div className="flex items-center gap-2.5">
                    <span
                      aria-hidden
                      className="grid size-8 flex-none place-items-center rounded-lg border border-line-strong text-[10px] font-bold text-up-bright"
                      style={{ background: "var(--accent-soft)" }}
                    >
                      {p.instrument.symbol.slice(0, 2)}
                    </span>
                    <div className="min-w-0">
                      <Sym className="text-[12.5px] font-semibold">{p.instrument.symbol}</Sym>
                      {!compact && p.instrument.name && (
                        <div className="truncate text-[10px] text-faint" dir="ltr">
                          {p.instrument.name}
                        </div>
                      )}
                    </div>
                    {p.price_quality === "delayed" && (
                      <span className="tag tag--warn ms-1">DELAYED</span>
                    )}
                  </div>
                </td>
                {hasSpark && (
                  <td className="py-2.5">
                    {series && series.length > 1 ? (
                      <Sparkline data={series} width={78} height={24} className="h-6 w-[78px]" />
                    ) : (
                      <span className="text-faint">—</span>
                    )}
                  </td>
                )}
                <td className="py-2.5 text-end"><Num value={p.quantity} kind="qty" /></td>
                <td className="py-2.5 text-end"><Num value={p.avg_cost} kind="price" /></td>
                <td className="py-2.5 text-end"><Num value={p.market_price} kind="price" flash /></td>
                <td className="py-2.5 text-end">
                  <Num value={p.market_value} currency={p.instrument.currency} flash />
                </td>
                <td className="py-2.5">
                  <span className="flex items-center justify-end gap-2" dir="ltr">
                    <span className="h-[5px] w-12 overflow-hidden rounded-full border border-line-strong bg-subtle">
                      <span
                        className="block h-full"
                        style={{
                          width: `${(weightPct * 100).toFixed(1)}%`,
                          background: "linear-gradient(90deg, var(--accent), var(--up-bright))",
                        }}
                      />
                    </span>
                    <Num value={p.weight} asPct />
                  </span>
                </td>
                <td className="py-2.5 text-end"><Num value={p.daily_pnl} signed flash /></td>
                <td className="py-2.5 text-end"><Num value={p.unrealized_pnl} signed flash /></td>
                <td className="py-2.5 text-end"><Num value={entryPct} asPct signed /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
