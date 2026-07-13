"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  PortfolioChart,
  type ChartMode,
  type CurvePoint,
} from "@/components/charts/portfolio-chart";
import { PositionsTable } from "@/components/positions/positions-table";
import { Num, Sym } from "@/components/ui/num";
import { Panel } from "@/components/ui/panel";
import { SourceBadge } from "@/components/ui/source-badge";
import { StatBlock } from "@/components/ui/stat-block";
import { Tabs } from "@/components/ui/tabs";
import { apiGet } from "@/lib/api";
import type { AccountSummary, BalancesResponse, PositionsResponse, Sourced } from "@/lib/types";

interface PerfSummary {
  available: boolean;
  as_of?: string;
  returns?: {
    total_twr: number;
    day: number | null;
    wtd: number | null;
    mtd: number | null;
    ytd: number | null;
  };
}

const CHART_MODES = [
  { value: "nav" as const, label: "שווי" },
  { value: "return" as const, label: "תשואה %" },
  { value: "drawdown" as const, label: "Drawdown" },
];

type Range = "1W" | "1M" | "3M" | "YTD" | "1Y" | "ALL";
const RANGES: Range[] = ["1W", "1M", "3M", "YTD", "1Y", "ALL"];
const RANGE_DAYS: Record<Range, number | null> = {
  "1W": 7,
  "1M": 31,
  "3M": 93,
  YTD: 0,
  "1Y": 366,
  ALL: null,
};

function filterByRange(points: CurvePoint[], range: Range): CurvePoint[] {
  if (points.length === 0) return points;
  const last = new Date(points[points.length - 1].date);
  let cutoff: Date;
  if (range === "YTD") cutoff = new Date(last.getFullYear(), 0, 1);
  else {
    const days = RANGE_DAYS[range];
    if (days == null) return points;
    cutoff = new Date(last);
    cutoff.setDate(cutoff.getDate() - days);
  }
  const filtered = points.filter((p) => new Date(p.date) >= cutoff);
  return filtered.length >= 2 ? filtered : points;
}

export default function OverviewPage() {
  const summary = useQuery({
    queryKey: ["account", "summary"],
    queryFn: () => apiGet<Sourced<AccountSummary>>("/account/summary"),
    refetchInterval: 30_000,
  });
  const balances = useQuery({
    queryKey: ["account", "balances"],
    queryFn: () => apiGet<BalancesResponse>("/account/balances"),
    refetchInterval: 60_000,
  });
  const positions = useQuery({
    queryKey: ["positions"],
    queryFn: () => apiGet<PositionsResponse>("/positions"),
    refetchInterval: 30_000,
  });
  const perf = useQuery({
    queryKey: ["performance", "summary"],
    queryFn: () => apiGet<PerfSummary>("/performance/summary"),
    refetchInterval: 120_000,
  });
  const curve = useQuery({
    queryKey: ["performance", "curve"],
    queryFn: () => apiGet<{ available: boolean; points: CurvePoint[] }>("/performance/equity-curve"),
    refetchInterval: 120_000,
  });
  const [mode, setMode] = useState<ChartMode>("nav");
  const [range, setRange] = useState<Range>("ALL");

  const a = summary.data?.data;
  const ccy = a?.base_currency ?? "USD";
  const r = perf.data?.returns;
  const dayPnl = a?.daily_pnl != null ? Number(a.daily_pnl) : null;
  const posRows = positions.data?.positions ?? [];

  const shownPoints = useMemo(
    () => (curve.data?.points ? filterByRange(curve.data.points, range) : []),
    [curve.data?.points, range],
  );

  // Exposure ladder: cash + each holding as a share of total assets.
  const exposure = useMemo(() => {
    if (!a) return null;
    const cash = Number(a.total_cash ?? 0);
    const rows = posRows
      .map((p) => ({
        label: p.instrument.symbol,
        value: Number(p.market_value ?? 0),
        kind: "position" as const,
      }))
      .filter((x) => x.value > 0)
      .sort((x, y) => y.value - x.value);
    const posTotal = rows.reduce((s, x) => s + x.value, 0);
    const base = Math.max(cash, 0) + posTotal;
    if (base <= 0) return null;
    const all = [{ label: "מזומן", value: Math.max(cash, 0), kind: "cash" as const }, ...rows];
    return { rows: all.map((x) => ({ ...x, pct: x.value / base })), base };
  }, [a, posRows]);

  const topHolding = useMemo(
    () =>
      posRows
        .filter((p) => Number(p.market_value ?? 0) > 0)
        .sort((x, y) => Number(y.market_value ?? 0) - Number(x.market_value ?? 0))[0],
    [posRows],
  );

  if (summary.isLoading) {
    return (
      <div className="grid grid-cols-12 gap-3.5">
        <div className="col-span-12 h-64 rounded-xl skeleton lg:col-span-8" />
        <div className="col-span-12 h-64 rounded-xl skeleton lg:col-span-4" />
      </div>
    );
  }

  if (!a) {
    return (
      <Panel title="סקירה כללית">
        <div className="py-10 text-center">
          <p className="t-h2">אין עדיין נתוני חשבון</p>
          <p className="mx-auto mt-1.5 max-w-md text-[12.5px] text-muted">
            כשה־IB Gateway יהיה מחובר, שווי החשבון, היתרות והפוזיציות יופיעו כאן ויתעדכנו בזמן אמת.
          </p>
        </div>
      </Panel>
    );
  }

  const topEntryPct =
    topHolding && topHolding.avg_cost != null && topHolding.market_price != null &&
    Number(topHolding.avg_cost) !== 0
      ? (Number(topHolding.market_price) - Number(topHolding.avg_cost)) / Number(topHolding.avg_cost)
      : null;

  return (
    <div className="grid grid-cols-12 items-start gap-3.5">
      {/* ── HERO: portfolio value + chart ─────────────────────────── */}
      <Panel
        className="col-span-12 lg:col-span-8"
        title="שווי התיק"
        subtitle="Net Liquidation"
        revealIndex={0}
        actions={
          <div className="flex items-center gap-1" dir="ltr">
            {RANGES.map((rg) => (
              <button
                key={rg}
                type="button"
                onClick={() => setRange(rg)}
                className={`press rounded-md px-2 py-1 text-[10.5px] font-medium transition-colors ${
                  range === rg
                    ? "bg-accent text-accent-fg"
                    : "text-faint hover:text-muted"
                }`}
              >
                {rg}
              </button>
            ))}
          </div>
        }
      >
        <div className="flex flex-wrap items-end justify-between gap-3 px-1 pb-2">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="t-hero">
                <Num value={a.net_liquidation} flash />
              </span>
              <span className="text-[12px] text-faint">{ccy}</span>
            </div>
            <div className="mt-2 flex items-center gap-2.5 text-[12.5px]">
              <span
                className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 font-semibold ${
                  (dayPnl ?? 0) < 0
                    ? "bg-[color-mix(in_srgb,var(--loss)_14%,transparent)] text-down-bright"
                    : "bg-accent-soft text-up-bright"
                }`}
              >
                <span className="text-[10px]">{(dayPnl ?? 0) < 0 ? "▼" : "▲"}</span>
                <Num value={dayPnl != null ? Math.abs(dayPnl) : null} />
              </span>
              <Num value={r?.day ?? null} asPct signed />
              <span className="text-faint">היום</span>
              {r?.total_twr != null && (
                <>
                  <span className="text-faint">·</span>
                  <Num value={r.total_twr} asPct signed />
                  <span className="text-faint">מצטבר</span>
                </>
              )}
            </div>
          </div>
          <Tabs items={CHART_MODES} value={mode} onChange={setMode} size="sm" ariaLabel="מצב גרף" />
        </div>

        {curve.isLoading ? (
          <div className="mx-1 h-[300px] rounded-lg skeleton" />
        ) : curve.data?.available && shownPoints.length >= 2 ? (
          <>
            <PortfolioChart points={shownPoints} mode={mode} currency={ccy} height={300} />
            <p className="t-help px-1">▲ הפקדה · ▼ משיכה — כדי שתזרים לא ייראה כרווח/הפסד.</p>
          </>
        ) : (
          <p className="py-16 text-center text-[12.5px] text-muted">
            הגרף יופיע לאחר סנכרון היסטוריה (מסך סנכרון).
          </p>
        )}
      </Panel>

      {/* ── RIGHT COL 1: exposure ladder + P&L ────────────────────── */}
      <div className="col-span-12 flex flex-col gap-3.5 lg:col-span-4">
        <Panel title="חשיפה והקצאה" revealIndex={1} padding="none"
          actions={<span className="tag">100%</span>}>
          {exposure ? (
            <div className="py-1.5">
              {exposure.rows.map((row) => (
                <div key={row.label} className="relative flex items-center justify-between px-3.5 py-2 text-[12.5px]">
                  <span
                    aria-hidden
                    className="absolute inset-y-0.5 start-0 rounded-e-md"
                    style={{
                      width: `${(row.pct * 100).toFixed(1)}%`,
                      background: row.kind === "cash" ? "var(--bg-hover)" : "var(--accent-soft)",
                    }}
                  />
                  <span className="relative z-10 flex items-center gap-2.5">
                    <span
                      aria-hidden
                      className="size-2 rounded-[3px]"
                      style={{ background: row.kind === "cash" ? "var(--fg-faint)" : "var(--accent)" }}
                    />
                    {row.kind === "cash" ? <span>מזומן</span> : <Sym>{row.label}</Sym>}
                  </span>
                  <span className="relative z-10 flex items-center gap-3 text-muted">
                    <Num value={row.value} />
                    <span className="w-10 text-end font-semibold text-fg"><Num value={row.pct} asPct /></span>
                  </span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-line px-3.5 py-2 text-[11px] text-faint">
                <span>שווי נכסים · <span className="sym">{ccy}</span></span>
                <span>מינוף <Num value={a.leverage} kind="qty" />×</span>
              </div>
            </div>
          ) : (
            <p className="px-3.5 py-6 text-center text-[12px] text-muted">אין נתוני הקצאה.</p>
          )}
        </Panel>

        <Panel title="רווח והפסד" subtitle="P&L" revealIndex={2} padding="none"
          actions={<span className="tag">היום</span>}>
          <PnlRow label="יומי" sub="Daily P&L" value={a.daily_pnl} ccy={ccy} />
          <PnlRow label="לא ממומש" sub="פוזיציות פתוחות" value={a.unrealized_pnl} ccy={ccy} />
          <PnlRow label="ממומש" sub="מומש היום" value={a.realized_pnl} ccy={ccy} last />
        </Panel>
      </div>

      {/* ── ASSET SPOTLIGHT (candlestick — real after price sync) ──── */}
      <Panel
        className="col-span-12 lg:col-span-8"
        title={topHolding ? topHolding.instrument.symbol : "החזקה מובילה"}
        subtitle={topHolding?.instrument.name ?? undefined}
        revealIndex={3}
        actions={
          topHolding ? (
            <div className="flex items-center gap-3">
              <span className="num text-[16px] font-semibold"><Num value={topHolding.market_price} kind="price" flash /></span>
              <Num value={topEntryPct} asPct signed />
              {topHolding.price_quality === "delayed" && <span className="tag tag--warn">DELAYED</span>}
            </div>
          ) : null
        }
      >
        <div className="flex h-[300px] flex-col items-center justify-center gap-3 text-center">
          <CandleGlyph />
          <div>
            <p className="text-[13px] font-medium text-muted">גרף נרות (Candlesticks) עם ממוצעים נעים ונפח</p>
            <p className="mx-auto mt-1 max-w-sm text-[11.5px] text-faint">
              יתווסף מיד לאחר סנכרון היסטוריית המחירים מ־IBKR. עד אז מוצגים כאן נתוני הפוזיציה בזמן אמת.
            </p>
          </div>
          {topHolding && (
            <div className="mt-1 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[12px]">
              <MiniStat label="כמות" value={topHolding.quantity} kind="qty" />
              <MiniStat label="מחיר ממוצע" value={topHolding.avg_cost} kind="price" />
              <MiniStat label="שווי שוק" value={topHolding.market_value} ccy={ccy} />
              <MiniStat label="לא ממומש" value={topHolding.unrealized_pnl} signed />
            </div>
          )}
        </div>
      </Panel>

      {/* ── RIGHT COL 2: margin & FX + news ───────────────────────── */}
      <div className="col-span-12 flex flex-col gap-3.5 lg:col-span-4">
        <Panel title="מרג'ין ומטבעות" revealIndex={4} padding="none">
          <PnlRow label="מרג'ין התחלתי" sub="Initial Margin" value={a.init_margin} ccy={ccy} plain />
          <PnlRow label="מרג'ין אחזקה" sub="Maintenance" value={a.maint_margin} ccy={ccy} plain />
          {balances.data && balances.data.balances.length > 0 && (
            <table className="w-full border-t border-line text-[12px]">
              <thead>
                <tr className="t-label">
                  <th className="px-3.5 pb-1 pt-2 text-start font-normal">מטבע</th>
                  <th className="px-3.5 pb-1 pt-2 text-end font-normal">מזומן</th>
                  <th className="px-3.5 pb-1 pt-2 text-end font-normal">שער לבסיס</th>
                </tr>
              </thead>
              <tbody>
                {balances.data.balances.map((b) => (
                  <tr key={b.currency} className="border-t border-line">
                    <td className="px-3.5 py-1.5"><Sym>{b.currency}</Sym></td>
                    <td className="px-3.5 py-1.5 text-end"><Num value={b.cash_balance} /></td>
                    <td className="px-3.5 py-1.5 text-end"><Num value={b.fx_rate_to_base} kind="price" className="text-faint" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="חדשות מהתיק" subtitle="Market Intelligence" revealIndex={5}
          actions={<span className="tag">בקרוב</span>}>
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <p className="text-[12.5px] text-muted">מרכז חדשות מקושר להחזקות</p>
            <p className="mx-auto max-w-[15rem] text-[11.5px] text-faint">
              חדשות רלוונטיות לכל נכס בתיק, עם דירוג רלוונטיות. מודול זה יופעל בהמשך (Finnhub).
            </p>
          </div>
        </Panel>
      </div>

      {/* ── POSITIONS ─────────────────────────────────────────────── */}
      <Panel
        className="col-span-12"
        title="פוזיציות פתוחות"
        revealIndex={6}
        actions={
          <div className="flex items-center gap-3 text-[11px] text-faint">
            <span>{posRows.length} פוזיציות</span>
            <SourceBadge source={positions.data?.source} stale={positions.data?.stale} />
          </div>
        }
      >
        <PositionsTable
          positions={posRows}
          nlv={a.net_liquidation ? Number(a.net_liquidation) : null}
        />
      </Panel>
    </div>
  );
}

function PnlRow({
  label,
  sub,
  value,
  ccy,
  last = false,
  plain = false,
}: {
  label: string;
  sub?: string;
  value: string | number | null | undefined;
  ccy?: string;
  last?: boolean;
  plain?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 px-3.5 py-3 ${last ? "" : "border-b border-line"}`}>
      <span className="text-[11.5px] text-muted">
        {label}
        {sub && <span className="mt-0.5 block text-[9.5px] text-faint">{sub}</span>}
      </span>
      <span className="num whitespace-nowrap text-[17px] font-semibold">
        <Num value={value} currency={ccy} signed={!plain} flash={!plain} />
      </span>
    </div>
  );
}

function MiniStat({
  label,
  value,
  kind = "money",
  ccy,
  signed,
}: {
  label: string;
  value: string | number | null | undefined;
  kind?: "money" | "price" | "qty";
  ccy?: string;
  signed?: boolean;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-faint">{label}</span>
      <Num value={value} kind={kind} currency={ccy} signed={signed} />
    </span>
  );
}

function CandleGlyph() {
  return (
    <svg width="52" height="40" viewBox="0 0 52 40" fill="none" aria-hidden className="glow-accent">
      <line x1="9" y1="6" x2="9" y2="34" stroke="var(--gain)" strokeWidth="1.5" />
      <rect x="5" y="12" width="8" height="16" rx="1.5" fill="var(--gain)" />
      <line x1="26" y1="3" x2="26" y2="30" stroke="var(--loss)" strokeWidth="1.5" />
      <rect x="22" y="10" width="8" height="14" rx="1.5" fill="var(--loss)" />
      <line x1="43" y1="8" x2="43" y2="37" stroke="var(--gain)" strokeWidth="1.5" />
      <rect x="39" y="18" width="8" height="14" rx="1.5" fill="var(--gain)" />
    </svg>
  );
}
