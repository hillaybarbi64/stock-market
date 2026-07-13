"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  PortfolioChart,
  type ChartMode,
  type CurvePoint,
} from "@/components/charts/portfolio-chart";
import { CandlestickChart, type Bar } from "@/components/charts/candlestick-chart";
import { Sparkline } from "@/components/charts/sparkline";
import { MoversList, type MoverRow } from "@/components/dashboard/movers-list";
import { PriceLadder } from "@/components/dashboard/price-ladder";
import { PositionsTable } from "@/components/positions/positions-table";
import { Num, Sym } from "@/components/ui/num";
import { Panel } from "@/components/ui/panel";
import { SourceBadge } from "@/components/ui/source-badge";
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

interface BarsResponse {
  available: boolean;
  series: Record<string, { symbol: string; name: string | null; bars: Bar[] }>;
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

// Candlestick timeframes: slice the daily-bar series to the last N trading days.
type TF = "1M" | "3M" | "6M" | "1Y" | "ALL";
const TFS: TF[] = ["1M", "3M", "6M", "1Y", "ALL"];
const TF_BARS: Record<TF, number | null> = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252, ALL: null };

const CHART_VIEWS = [
  { value: "instrument" as const, label: "נכס" },
  { value: "portfolio" as const, label: "התיק" },
];
type ChartView = "instrument" | "portfolio";

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
  const bars = useQuery({
    queryKey: ["positions", "bars"],
    queryFn: () => apiGet<BarsResponse>("/positions/bars?days=180"),
    refetchInterval: 300_000,
  });

  const [mode, setMode] = useState<ChartMode>("nav");
  const [range, setRange] = useState<Range>("ALL");
  const [view, setView] = useState<ChartView>("instrument");
  const [tf, setTf] = useState<TF>("3M");
  const [picked, setPicked] = useState<number | null>(null);

  const a = summary.data?.data;
  const ccy = a?.base_currency ?? "USD";
  const r = perf.data?.returns;
  const dayPnl = a?.daily_pnl != null ? Number(a.daily_pnl) : null;
  const posRows = useMemo(() => positions.data?.positions ?? [], [positions.data]);
  const series = bars.data?.series;

  const shownPoints = useMemo(
    () => (curve.data?.points ? filterByRange(curve.data.points, range) : []),
    [curve.data, range],
  );

  // conid → recent closes, for sparklines everywhere on the page.
  const sparklines = useMemo(() => {
    const map: Record<number, number[]> = {};
    if (series) {
      for (const [conid, s] of Object.entries(series)) {
        if (s.bars.length > 1) map[Number(conid)] = s.bars.slice(-30).map((b) => b.close);
      }
    }
    return map;
  }, [series]);

  // Portfolio "movers": one row per holding, biggest first, with the last close,
  // the day-over-day % move (from the bar series) and an inline sparkline.
  const moverRows = useMemo<MoverRow[]>(() => {
    return posRows
      .filter((p) => Number(p.market_value ?? 0) > 0)
      .sort((x, y) => Number(y.market_value ?? 0) - Number(x.market_value ?? 0))
      .map((p) => {
        const conid = p.instrument.conid;
        const b = series?.[String(conid)]?.bars ?? [];
        const last = p.market_price != null ? Number(p.market_price) : b.at(-1)?.close ?? null;
        const prev = b.length >= 2 ? b[b.length - 2].close : null;
        const cur = b.at(-1)?.close ?? last;
        const changePct = prev != null && cur != null && prev !== 0 ? (cur - prev) / prev : null;
        return {
          conid,
          symbol: p.instrument.symbol,
          name: p.instrument.name,
          last,
          changePct,
          spark: sparklines[conid] ?? [],
          delayed: p.price_quality === "delayed",
        };
      });
  }, [posRows, series, sparklines]);

  // Resolve the active instrument (user pick, else biggest holding).
  const activeConid =
    picked != null && moverRows.some((m) => m.conid === picked) ? picked : moverRows[0]?.conid ?? null;
  const selPos = posRows.find((p) => p.instrument.conid === activeConid) ?? null;
  const selMover = moverRows.find((m) => m.conid === activeConid) ?? null;
  const selBars = useMemo(
    () => (activeConid != null ? series?.[String(activeConid)]?.bars ?? [] : []),
    [activeConid, series],
  );
  const tfBars = useMemo(() => {
    const n = TF_BARS[tf];
    return n == null ? selBars : selBars.slice(-n);
  }, [selBars, tf]);
  const lastBar = tfBars.at(-1) ?? null;
  const prevBar = tfBars.length >= 2 ? tfBars[tfBars.length - 2] : null;
  const selPrice = selPos?.market_price != null ? Number(selPos.market_price) : lastBar?.close ?? null;
  const selAvg = selPos?.avg_cost != null ? Number(selPos.avg_cost) : null;

  const equitySpark = useMemo(
    () => (curve.data?.points ?? []).slice(-48).map((p) => p.nav),
    [curve.data?.points],
  );

  if (summary.isLoading) {
    return (
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 h-[520px] rounded-xl skeleton xl:col-span-3" />
        <div className="col-span-12 h-[520px] rounded-xl skeleton xl:col-span-6" />
        <div className="col-span-12 h-[520px] rounded-xl skeleton xl:col-span-3" />
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

  return (
    <div className="grid grid-cols-12 items-start gap-3">
      {/* ── LEFT RAIL: account + overview + movers ─────────────────── */}
      <div className="col-span-12 flex flex-col gap-3 xl:col-span-3">
        <Panel revealIndex={0} padding="none" grip={false}>
          <div className="px-3.5 pb-3 pt-3.5">
            <div className="flex items-center justify-between">
              <span className="t-label t-label-upper" dir="ltr">
                Individual
              </span>
              <span className="tag">{"מרג'ין"}</span>
            </div>
            <div className="mt-1.5 flex items-baseline gap-1.5">
              <span className="t-hero">
                <Num value={a.net_liquidation} flash />
              </span>
              <span className="text-[11px] text-faint">{ccy}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-[12px]">
              <span
                className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold ${
                  (dayPnl ?? 0) < 0
                    ? "bg-[color-mix(in_srgb,var(--loss)_14%,transparent)] text-down-bright"
                    : "bg-accent-soft text-up-bright"
                }`}
              >
                <span className="text-[9px]">{(dayPnl ?? 0) < 0 ? "▼" : "▲"}</span>
                <Num value={dayPnl != null ? Math.abs(dayPnl) : null} />
              </span>
              <Num value={r?.day ?? null} asPct signed />
              <span className="text-faint">היום</span>
            </div>
            {equitySpark.length >= 2 && (
              <Sparkline
                data={equitySpark}
                width={260}
                height={34}
                tone={(r?.total_twr ?? 0) < 0 ? "loss" : "accent"}
                className="mt-2.5 h-[34px] w-full"
              />
            )}
          </div>
          <div className="border-t border-line">
            <StatRow label="כוח קנייה" en="Buying power" value={a.buying_power} />
            <StatRow label="מזומן" en="Cash" value={a.total_cash} />
            <StatRow label="עודף נזילות" en="Excess liquidity" value={a.excess_liquidity} />
            <StatRow label="מרג'ין אחזקה" en="Maint. margin" value={a.maint_margin} />
            <StatRow label="מינוף" en="Leverage" value={a.leverage} kind="qty" suffix="×" last />
          </div>
        </Panel>

        <Panel
          title="המובילים בתיק"
          subtitle="Movers"
          revealIndex={1}
          padding="none"
          actions={<span className="tag">{moverRows.length}</span>}
        >
          <MoversList rows={moverRows} selected={activeConid} onSelect={setPicked} />
        </Panel>
      </div>

      {/* ── CENTRE: chart terminal + account detail band ───────────── */}
      <div className="col-span-12 flex flex-col gap-3 xl:col-span-6">
      <Panel
        revealIndex={2}
        padding="none"
        grip={false}
        title={view === "instrument" ? selMover?.symbol ?? "נכס" : "שווי התיק"}
        subtitle={view === "instrument" ? selMover?.name ?? undefined : "Net Liquidation"}
        info={
          view === "instrument" && selMover?.delayed ? <span className="tag tag--warn">DELAYED</span> : null
        }
        actions={
          <Tabs items={CHART_VIEWS} value={view} onChange={setView} size="sm" ariaLabel="תצוגת גרף" />
        }
      >
        {view === "instrument" ? (
          <div>
            {/* OHLC readout strip */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-3.5 py-2">
              <div className="flex items-baseline gap-1.5">
                <span className="num text-[18px] font-semibold">
                  <Num value={selPrice} kind="price" flash />
                </span>
                {prevBar && lastBar && prevBar.close !== 0 && (
                  <Num
                    value={(lastBar.close - prevBar.close) / prevBar.close}
                    asPct
                    signed
                    className="text-[12px]"
                  />
                )}
              </div>
              {lastBar && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px]" dir="ltr">
                  <Ohlc label="O" value={lastBar.open} />
                  <Ohlc label="H" value={lastBar.high} />
                  <Ohlc label="L" value={lastBar.low} />
                  <Ohlc label="C" value={lastBar.close} />
                  <span className="flex items-center gap-1">
                    <span className="text-faint">V</span>
                    <Num value={lastBar.volume} kind="qty" className="text-muted" />
                  </span>
                </div>
              )}
              <div className="ms-auto flex items-center gap-3 text-[10px]" dir="ltr">
                <LegendDot color="var(--warn)" label="MA7" />
                <LegendDot color="var(--info)" label="MA25" />
              </div>
            </div>

            {tfBars.length > 1 ? (
              <>
                <CandlestickChart bars={tfBars} height={392} currency={ccy} />
                <div className="flex items-center justify-between border-t border-line px-3 py-1.5">
                  <div className="flex items-center gap-1" dir="ltr">
                    {TFS.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setTf(t)}
                        className={`press rounded-md px-2 py-0.5 text-[10.5px] font-medium transition-colors ${
                          tf === t ? "bg-accent text-accent-fg" : "text-faint hover:text-muted"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <span className="chip text-[10px]" dir="ltr">
                    <span className="text-faint">Interval</span> 1D
                  </span>
                </div>
              </>
            ) : (
              <div className="flex h-[392px] flex-col items-center justify-center gap-3 px-6 text-center">
                <CandleGlyph />
                <p className="text-[12.5px] text-muted">גרף נרות יופיע לאחר סנכרון היסטוריית מחירים מ־IBKR.</p>
                {selPos && (
                  <div className="mt-1 flex flex-wrap justify-center gap-x-5 gap-y-1.5 text-[12px]">
                    <MiniStat label="כמות" value={selPos.quantity} kind="qty" />
                    <MiniStat label="מחיר ממוצע" value={selPos.avg_cost} kind="price" />
                    <MiniStat label="שווי שוק" value={selPos.market_value} ccy={ccy} />
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="p-3.5">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-baseline gap-2">
                <span className="t-hero">
                  <Num value={a.net_liquidation} flash />
                </span>
                {r?.total_twr != null && (
                  <span className="flex items-center gap-1 text-[12px]">
                    <Num value={r.total_twr} asPct signed />
                    <span className="text-faint">מצטבר</span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2" dir="ltr">
                <Tabs items={CHART_MODES} value={mode} onChange={setMode} size="sm" ariaLabel="מצב גרף" />
                <div className="flex items-center gap-1">
                  {RANGES.map((rg) => (
                    <button
                      key={rg}
                      type="button"
                      onClick={() => setRange(rg)}
                      className={`press rounded-md px-2 py-1 text-[10.5px] font-medium transition-colors ${
                        range === rg ? "bg-accent text-accent-fg" : "text-faint hover:text-muted"
                      }`}
                    >
                      {rg}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            {curve.data?.available && shownPoints.length >= 2 ? (
              <>
                <PortfolioChart points={shownPoints} mode={mode} currency={ccy} height={360} />
                <p className="t-help px-1">▲ הפקדה · ▼ משיכה — כדי שתזרים לא ייראה כרווח/הפסד.</p>
              </>
            ) : (
              <p className="py-24 text-center text-[12.5px] text-muted">
                עקומת ההון תופיע לאחר סנכרון היסטוריה (מסך סנכרון).
              </p>
            )}
          </div>
        )}
      </Panel>

      {/* Account-detail band: margin, funds & FX — fills the column and
          keeps the terminal dense, like the Legend account overview. */}
      <Panel title="פרטי חשבון" subtitle="Margin & FX" revealIndex={4} padding="none" grip={false}>
        <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
          <DetailCell label="מרג'ין התחלתי" en="Init margin" value={a.init_margin} />
          <DetailCell label="מרג'ין אחזקה" en="Maint. margin" value={a.maint_margin} />
          <DetailCell label="כספים זמינים" en="Avail. funds" value={a.available_funds} />
          <DetailCell label="שווי פוזיציות" en="Gross value" value={a.gross_position_value} />
        </div>
        {balances.data && balances.data.balances.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line px-3.5 py-2.5">
            <span className="t-label">מטבעות</span>
            {balances.data.balances.map((b) => (
              <span key={b.currency} className="flex items-center gap-1.5 text-[11.5px]" dir="ltr">
                <Sym className="text-faint">{b.currency}</Sym>
                <Num value={b.cash_balance} />
                <span className="text-[9.5px] text-faint">@{Number(b.fx_rate_to_base ?? 1).toFixed(4)}</span>
              </span>
            ))}
          </div>
        )}
      </Panel>
      </div>

      {/* ── RIGHT RAIL: price ladder + position P&L ────────────────── */}
      <div className="col-span-12 flex flex-col gap-3 xl:col-span-3">
        <Panel
          title={selMover ? selMover.symbol : "סולם מחיר"}
          subtitle="Volume by price"
          revealIndex={3}
          padding="none"
          grip={false}
        >
          {selPos && (
            <div className="grid grid-cols-2 gap-px border-b border-line bg-line text-[11px]">
              <div className="bg-panel px-3 py-2">
                <div className="t-label">P&L לא ממומש</div>
                <div className="num mt-0.5 text-[15px] font-semibold">
                  <Num value={selPos.unrealized_pnl} signed flash />
                </div>
              </div>
              <div className="bg-panel px-3 py-2">
                <div className="t-label">כמות @ ממוצע</div>
                <div className="num mt-0.5 text-[13px] text-muted" dir="ltr">
                  <Num value={selPos.quantity} kind="qty" /> @ <Num value={selPos.avg_cost} kind="price" />
                </div>
              </div>
            </div>
          )}
          <PriceLadder bars={selBars} last={selPrice} avgCost={selAvg} />
        </Panel>

        <Panel title="רווח והפסד" subtitle="P&L" revealIndex={4} padding="none" grip={false}>
          <PnlRow label="יומי" en="Daily" value={a.daily_pnl} ccy={ccy} />
          <PnlRow label="לא ממומש" en="Unrealized" value={a.unrealized_pnl} ccy={ccy} />
          <PnlRow label="ממומש" en="Realized" value={a.realized_pnl} ccy={ccy} last />
        </Panel>
      </div>

      {/* ── POSITIONS ──────────────────────────────────────────────── */}
      <Panel
        className="col-span-12"
        title="פוזיציות פתוחות"
        revealIndex={5}
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
          sparklines={sparklines}
        />
      </Panel>
    </div>
  );
}

function StatRow({
  label,
  en,
  value,
  kind = "money",
  suffix,
  last = false,
}: {
  label: string;
  en: string;
  value: string | number | null | undefined;
  kind?: "money" | "price" | "qty";
  suffix?: string;
  last?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 px-3.5 py-[7px] ${last ? "" : "border-b border-line/60"}`}
    >
      <span className="text-[11.5px] text-muted">
        {label}
        <span className="ms-1.5 text-[9.5px] text-faint" dir="ltr">
          {en}
        </span>
      </span>
      <span className="num whitespace-nowrap text-[12.5px] font-medium">
        <Num value={value} kind={kind} />
        {suffix}
      </span>
    </div>
  );
}

function DetailCell({
  label,
  en,
  value,
}: {
  label: string;
  en: string;
  value: string | number | null | undefined;
}) {
  return (
    <div className="bg-panel px-3.5 py-2.5">
      <div className="flex items-baseline gap-1.5">
        <span className="text-[11px] text-muted">{label}</span>
        <span className="text-[9px] text-faint" dir="ltr">
          {en}
        </span>
      </div>
      <div className="num mt-0.5 text-[14px] font-semibold">
        <Num value={value} />
      </div>
    </div>
  );
}

function PnlRow({
  label,
  en,
  value,
  ccy,
  last = false,
}: {
  label: string;
  en?: string;
  value: string | number | null | undefined;
  ccy?: string;
  last?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 px-3.5 py-2.5 ${last ? "" : "border-b border-line"}`}
    >
      <span className="text-[11.5px] text-muted">
        {label}
        {en && (
          <span className="ms-1.5 text-[9.5px] text-faint" dir="ltr">
            {en}
          </span>
        )}
      </span>
      <span className="num whitespace-nowrap text-[15px] font-semibold">
        <Num value={value} currency={ccy} signed flash />
      </span>
    </div>
  );
}

function Ohlc({ label, value }: { label: string; value: number }) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-faint">{label}</span>
      <Num value={value} kind="price" className="text-muted" />
    </span>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1 text-faint">
      <i className="inline-block h-0.5 w-3 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function MiniStat({
  label,
  value,
  kind = "money",
  ccy,
}: {
  label: string;
  value: string | number | null | undefined;
  kind?: "money" | "price" | "qty";
  ccy?: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-faint">{label}</span>
      <Num value={value} kind={kind} currency={ccy} />
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
