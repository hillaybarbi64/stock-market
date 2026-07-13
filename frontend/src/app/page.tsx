"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  PortfolioChart,
  type ChartMode,
  type CurvePoint,
} from "@/components/charts/portfolio-chart";
import { PositionsTable } from "@/components/positions/positions-table";
import { Num } from "@/components/ui/num";
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

  const a = summary.data?.data;
  const ccy = a?.base_currency ?? "USD";
  const r = perf.data?.returns;
  const dayPnl = a?.daily_pnl != null ? Number(a.daily_pnl) : null;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="t-h1">סקירה כללית</h1>
        <SourceBadge source={summary.data?.source} stale={summary.data?.stale} asOf={summary.data?.as_of} />
      </div>

      {summary.isLoading ? (
        <div className="h-44 rounded-md skeleton" />
      ) : !a ? (
        <Panel>
          <div className="py-8 text-center">
            <p className="t-h2">אין עדיין נתוני חשבון</p>
            <p className="mx-auto mt-1 max-w-md text-[12.5px] text-muted">
              כשה־IB Gateway יהיה מחובר, שווי החשבון, היתרות והפוזיציות יופיעו כאן ויתעדכנו בזמן אמת.
            </p>
          </div>
        </Panel>
      ) : (
        <>
          {/* Hero — one primary metric, a supporting strip */}
          <Panel elevation="raised" revealIndex={0}>
            <div className="grid gap-5 lg:grid-cols-[minmax(220px,auto)_1fr] lg:items-center">
              <div className="lg:border-e lg:border-line lg:pe-6">
                <StatBlock
                  label="שווי חשבון · Net Liquidation"
                  value={a.net_liquidation}
                  currency={ccy}
                  flash
                  primary
                  delta={dayPnl}
                  deltaPct={r?.day ?? undefined}
                  meta={{
                    what: "שווי כל הנכסים והמזומן בחשבון, במטבע הבסיס.",
                    source: summary.data?.source ?? undefined,
                    updated: summary.data?.as_of ?? undefined,
                    currency: ccy,
                    live: !summary.data?.stale,
                  }}
                />
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
                <StatBlock label="תשואה YTD" value={r?.ytd ?? null} asPct signed
                  meta={{ what: "תשואת התיק מתחילת השנה (TWR).", how: "TWR יומי משורשר בנטרול הפקדות/משיכות.", source: "computed", live: false }} />
                <StatBlock label="תשואה מצטברת" value={r?.total_twr ?? null} asPct signed
                  meta={{ what: "תשואה מצטברת מאז תחילת ההיסטוריה (TWR).", source: "computed", live: false }} />
                <StatBlock label="מזומן" value={a.total_cash} currency={ccy} flash />
                <StatBlock label="כוח קנייה" value={a.buying_power} currency={ccy} />
                <StatBlock label="שווי פוזיציות" value={a.gross_position_value} currency={ccy} />
              </div>
            </div>
          </Panel>

          {/* Central chart */}
          <Panel
            title="עקומת התיק"
            revealIndex={1}
            actions={<Tabs items={CHART_MODES} value={mode} onChange={setMode} size="sm" ariaLabel="מצב גרף" />}
          >
            {curve.isLoading ? (
              <div className="h-[300px] rounded-sm skeleton" />
            ) : curve.data?.available ? (
              <>
                <PortfolioChart points={curve.data.points} mode={mode} currency={ccy} height={300} />
                <p className="t-help mt-1">▲ הפקדה · ▼ משיכה — כדי שתזרים לא ייראה כרווח/הפסד.</p>
              </>
            ) : (
              <p className="py-16 text-center text-[12.5px] text-muted">
                הגרף יופיע לאחר סנכרון היסטוריה (מסך סנכרון).
              </p>
            )}
          </Panel>

          {/* P&L + margin/currencies */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="רווח והפסד" revealIndex={2}>
              <div className="grid grid-cols-3 gap-x-6 gap-y-4">
                <StatBlock label="P&L יומי" value={a.daily_pnl} currency={ccy} signed flash
                  meta={{ what: "רווח/הפסד היום.", source: "ibkr_gateway", live: true, currency: ccy }} />
                <StatBlock label="לא ממומש" value={a.unrealized_pnl} currency={ccy} signed flash
                  meta={{ what: "רווח/הפסד על פוזיציות פתוחות שטרם נמכרו.", source: "ibkr_gateway", live: true }} />
                <StatBlock label="ממומש (היום)" value={a.realized_pnl} currency={ccy} signed flash
                  meta={{ what: "רווח/הפסד שמומש היום ממכירות.", source: "ibkr_gateway", live: true }} />
              </div>
            </Panel>

            <Panel title="מרג'ין ומטבעות" revealIndex={3}>
              <div className="grid grid-cols-3 gap-x-6 gap-y-4">
                <StatBlock label="Initial Margin" value={a.init_margin} currency={ccy} />
                <StatBlock label="Maintenance" value={a.maint_margin} currency={ccy} />
                <StatBlock label="מינוף" value={a.leverage} kind="qty"
                  meta={{ what: "חשיפה ברוטו חלקי שווי החשבון.", source: "computed" }} />
              </div>
              {balances.data && balances.data.balances.length > 0 && (
                <table className="mt-3 w-full text-[12px]">
                  <thead>
                    <tr className="t-label">
                      <th className="pb-1 text-start font-normal">מטבע</th>
                      <th className="pb-1 text-end font-normal">מזומן</th>
                      <th className="pb-1 text-end font-normal">שער לבסיס</th>
                    </tr>
                  </thead>
                  <tbody>
                    {balances.data.balances.map((b) => (
                      <tr key={b.currency} className="border-t border-line">
                        <td className="py-1"><span className="sym">{b.currency}</span></td>
                        <td className="py-1 text-end"><Num value={b.cash_balance} /></td>
                        <td className="py-1 text-end"><Num value={b.fx_rate_to_base} kind="price" className="text-faint" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </div>

          {/* Positions */}
          <Panel
            title="פוזיציות פתוחות"
            revealIndex={4}
            actions={<SourceBadge source={positions.data?.source} stale={positions.data?.stale} />}
          >
            <PositionsTable
              positions={positions.data?.positions ?? []}
              nlv={a.net_liquidation ? Number(a.net_liquidation) : null}
              compact
            />
          </Panel>
        </>
      )}
    </div>
  );
}
