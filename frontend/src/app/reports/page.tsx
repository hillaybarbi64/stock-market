"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Num, Sym } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Periodic {
  available: boolean;
  detail?: string;
  from: string;
  to: string;
  nav_start: number;
  nav_end: number;
  twr: number;
  max_drawdown: number;
  deposits: number;
  withdrawals: number;
  dividends: number;
  fees_cash: number;
  interest_net: number;
  trades_count: number;
  best_cycles: { symbol: string; direction: string; realized_pnl: number; closed: string }[];
  worst_cycles: { symbol: string; direction: string; realized_pnl: number; closed: string }[];
  method_note: string;
}

function defaultRange(kind: string): [string, string] {
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  const d = new Date(now);
  if (kind === "week") d.setDate(d.getDate() - 7);
  else if (kind === "month") d.setMonth(d.getMonth() - 1);
  else if (kind === "quarter") d.setMonth(d.getMonth() - 3);
  else if (kind === "year") d.setFullYear(d.getFullYear() - 1);
  else d.setMonth(0, 1);
  return [d.toISOString().slice(0, 10), to];
}

export default function ReportsPage() {
  const [[from, to], setRange] = useState<[string, string]>(() => defaultRange("month"));

  const report = useQuery({
    queryKey: ["report", from, to],
    queryFn: () => apiGet<Periodic>(`/reports/periodic?date_from=${from}&date_to=${to}`),
    enabled: Boolean(from && to),
  });

  const r = report.data;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <h1 className="text-[17px] font-semibold tracking-tight">דוחות</h1>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={!r?.available}
          className="rounded-sm border border-line px-3 py-1 text-[12px] text-muted hover:bg-hover hover:text-fg disabled:opacity-40"
        >
          הדפס / שמור כ-PDF
        </button>
      </div>

      <Panel className="print:hidden">
        <div className="flex flex-wrap items-end gap-3">
          {[
            ["week", "שבוע"],
            ["month", "חודש"],
            ["quarter", "רבעון"],
            ["ytd", "מתחילת השנה"],
            ["year", "שנה"],
          ].map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setRange(defaultRange(k))}
              className="rounded-sm border border-line px-2.5 py-1 text-[11.5px] text-muted hover:bg-hover hover:text-fg"
            >
              {label}
            </button>
          ))}
          <label className="flex flex-col gap-1 text-[10.5px] text-faint">
            מתאריך
            <input type="date" value={from} onChange={(e) => setRange([e.target.value, to])}
              className="num rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none" />
          </label>
          <label className="flex flex-col gap-1 text-[10.5px] text-faint">
            עד
            <input type="date" value={to} onChange={(e) => setRange([from, e.target.value])}
              className="num rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none" />
          </label>
          <div className="ms-auto flex gap-2">
            {[
              ["trades.csv", "עסקאות"],
              ["cycles.csv", "מחזורים"],
              ["daily_equity.csv", "NAV יומי"],
            ].map(([file, label]) => (
              <a key={file} href={`${API_URL}/api/reports/export/${file}`}
                className="rounded-sm border border-line px-2.5 py-1 text-[11.5px] text-muted hover:bg-hover hover:text-fg">
                ⬇ {label}
              </a>
            ))}
          </div>
        </div>
      </Panel>

      {report.isLoading ? (
        <div className="h-60 animate-pulse rounded-md bg-subtle" />
      ) : !r?.available ? (
        <Panel>
          <p className="py-10 text-center text-[12.5px] text-muted">{r?.detail ?? "בחר טווח תאריכים"}</p>
        </Panel>
      ) : (
        <div className="rounded-md border border-line bg-panel p-6 print:border-0">
          <header className="border-b border-line pb-4">
            <h2 className="text-[16px] font-semibold">דוח תקופתי</h2>
            <p className="num mt-0.5 text-[12px] text-muted">{r.from} → {r.to}</p>
          </header>

          <section className="grid grid-cols-2 gap-x-8 gap-y-4 py-4 sm:grid-cols-4">
            <RS label="שווי בתחילת התקופה" v={<Num value={r.nav_start} currency="USD" />} />
            <RS label="שווי בסוף התקופה" v={<Num value={r.nav_end} currency="USD" />} />
            <RS label="תשואה (TWR)" v={<Num value={r.twr} asPct signed />} />
            <RS label="Drawdown מקסימלי" v={<Num value={r.max_drawdown} asPct signed />} />
            <RS label="הפקדות" v={<Num value={r.deposits} />} />
            <RS label="משיכות" v={<Num value={r.withdrawals} />} />
            <RS label="דיבידנדים" v={<Num value={r.dividends} />} />
            <RS label="ריבית (נטו)" v={<Num value={r.interest_net} signed />} />
            <RS label="מספר ביצועים" v={<span className="num">{r.trades_count}</span>} />
          </section>

          <section className="grid gap-6 border-t border-line py-4 sm:grid-cols-2">
            <CycleList title="עסקאות מובילות" rows={r.best_cycles} />
            <CycleList title="עסקאות חלשות" rows={r.worst_cycles} />
          </section>

          <footer className="border-t border-line pt-3 text-[10px] text-faint">
            {r.method_note} · הופק {new Date().toLocaleString("he-IL")} · Live Read-Only
          </footer>
        </div>
      )}
    </div>
  );
}

function RS({ label, v }: { label: string; v: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[15px] font-semibold">{v}</div>
    </div>
  );
}

function CycleList({
  title,
  rows,
}: {
  title: string;
  rows: { symbol: string; direction: string; realized_pnl: number; closed: string }[];
}) {
  return (
    <div>
      <h3 className="mb-1.5 text-[12px] font-medium text-muted">{title}</h3>
      {rows.length ? (
        rows.map((c, idx) => (
          <div key={idx} className="flex items-center justify-between border-t border-line py-1 text-[12.5px]">
            <span className="flex items-center gap-2">
              <Sym>{c.symbol}</Sym>
              <span className="sym text-[9.5px] text-faint">{c.direction}</span>
              <span className="num text-[10px] text-faint">{c.closed}</span>
            </span>
            <Num value={c.realized_pnl} signed />
          </div>
        ))
      ) : (
        <p className="text-[11.5px] text-faint">אין עסקאות סגורות בתקופה.</p>
      )}
    </div>
  );
}
