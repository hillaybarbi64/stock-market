"use client";

import { useMemo, useState } from "react";
import { Num, Sym } from "@/components/ui/num";
import type { PositionRow } from "@/lib/types";

type SortKey = "symbol" | "market_value" | "unrealized_pnl" | "daily_pnl" | "weight";

/*
  Positions table. Row order is stable while prices tick (sorted by the chosen
  key only when data identity changes, not per tick) to avoid jumpy layouts.
*/
export function PositionsTable({
  positions,
  nlv,
  compact = false,
}: {
  positions: PositionRow[];
  nlv: number | null;
  compact?: boolean;
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

  if (positions.length === 0) {
    return (
      <p className="py-6 text-center text-[12.5px] text-muted">
        אין פוזיציות פתוחות להצגה.
      </p>
    );
  }

  const th = (key: SortKey, label: string, numeric = true) => (
    <th
      className={`cursor-pointer select-none pb-1.5 font-normal text-[10.5px] text-faint hover:text-muted ${
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
          <tr>
            {th("symbol", "נכס", false)}
            <th className="pb-1.5 text-end text-[10.5px] font-normal text-faint">כמות</th>
            <th className="pb-1.5 text-end text-[10.5px] font-normal text-faint">מחיר ממוצע</th>
            <th className="pb-1.5 text-end text-[10.5px] font-normal text-faint">מחיר נוכחי</th>
            {th("market_value", "שווי שוק")}
            {th("weight", "משקל בתיק")}
            {th("daily_pnl", "P&L יומי")}
            {th("unrealized_pnl", "P&L לא ממומש")}
            <th className="pb-1.5 text-end text-[10.5px] font-normal text-faint">מהכניסה %</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const entryPct =
              p.avg_cost != null && p.market_price != null && Number(p.avg_cost) !== 0
                ? (Number(p.market_price) - Number(p.avg_cost)) / Number(p.avg_cost)
                : null;
            return (
              <tr
                key={p.instrument.conid}
                className="border-t border-line transition-colors duration-[120ms] hover:bg-hover"
              >
                <td className="py-1.5">
                  <div className="flex items-baseline gap-2">
                    <Sym className="text-[12.5px]">{p.instrument.symbol}</Sym>
                    {!compact && p.instrument.name && (
                      <span className="truncate text-[11px] text-faint" dir="ltr">
                        {p.instrument.name}
                      </span>
                    )}
                    {p.price_quality === "delayed" && (
                      <span className="sym rounded-sm bg-subtle px-1 text-[8.5px] text-warn">
                        DELAYED
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-1.5 text-end"><Num value={p.quantity} kind="qty" /></td>
                <td className="py-1.5 text-end"><Num value={p.avg_cost} kind="price" /></td>
                <td className="py-1.5 text-end"><Num value={p.market_price} kind="price" flash /></td>
                <td className="py-1.5 text-end">
                  <Num value={p.market_value} currency={p.instrument.currency} flash />
                </td>
                <td className="py-1.5 text-end"><Num value={p.weight} asPct /></td>
                <td className="py-1.5 text-end"><Num value={p.daily_pnl} signed flash /></td>
                <td className="py-1.5 text-end"><Num value={p.unrealized_pnl} signed flash /></td>
                <td className="py-1.5 text-end"><Num value={entryPct} asPct signed /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
