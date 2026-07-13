"use client";

/*
  MoversList — the Legend left-rail "market movers" table, mapped to the real
  portfolio: one dense row per holding with a rank, ticker, inline sparkline,
  last price and the day's % change. Rows are selectable — clicking one loads
  that instrument into the centre chart and the right-rail ladder, exactly like
  clicking a symbol in the Legend terminal. Renders LTR (numbers/tickers read
  left→right) inside the RTL page.
*/

import { Sparkline } from "@/components/charts/sparkline";
import { Num, Sym } from "@/components/ui/num";

export interface MoverRow {
  conid: number;
  symbol: string;
  name: string | null;
  last: number | null;
  changePct: number | null; // fraction, e.g. 0.0123
  spark: number[];
  delayed: boolean;
}

export function MoversList({
  rows,
  selected,
  onSelect,
}: {
  rows: MoverRow[];
  selected: number | null;
  onSelect: (conid: number) => void;
}) {
  if (rows.length === 0) {
    return <p className="px-3.5 py-6 text-center text-[12px] text-muted">אין החזקות להצגה.</p>;
  }
  return (
    <div className="flex flex-col" dir="ltr">
      <div className="grid grid-cols-[16px_1fr_54px_60px] items-center gap-2 border-b border-line px-3 py-1.5 t-label">
        <span>#</span>
        <span>Symbol</span>
        <span className="text-end">Last</span>
        <span className="text-end">Chg%</span>
      </div>
      {rows.map((row, i) => {
        const active = row.conid === selected;
        return (
          <button
            key={row.conid}
            type="button"
            onClick={() => onSelect(row.conid)}
            aria-pressed={active}
            className={`nav-item press grid grid-cols-[16px_1fr_54px_60px] items-center gap-2 border-b border-line/60 px-3 py-[7px] text-start transition-colors ${
              active
                ? "nav-item--active bg-[linear-gradient(90deg,var(--accent-soft),transparent)]"
                : "hover:bg-hover"
            }`}
          >
            <span className="text-[10px] tabular-nums text-faint">{i + 1}</span>
            <span className="flex min-w-0 items-center gap-2">
              <Sym className={`truncate text-[12px] ${active ? "text-fg" : ""}`}>{row.symbol}</Sym>
              <Sparkline
                data={row.spark}
                width={40}
                height={15}
                strokeWidth={1.1}
                fill={false}
                className="h-[15px] w-10 shrink-0"
              />
            </span>
            <span className="text-end text-[11.5px]">
              <Num value={row.last} kind="price" />
            </span>
            <span className="text-end text-[11.5px]">
              <Num value={row.changePct} asPct signed />
            </span>
          </button>
        );
      })}
    </div>
  );
}
