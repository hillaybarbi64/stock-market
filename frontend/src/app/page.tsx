"use client";

import { useQuery } from "@tanstack/react-query";
import { PositionsTable } from "@/components/positions/positions-table";
import { Panel } from "@/components/ui/panel";
import { SourceBadge } from "@/components/ui/source-badge";
import { Stat } from "@/components/ui/stat";
import { apiGet } from "@/lib/api";
import type { AccountSummary, BalancesResponse, PositionsResponse, Sourced } from "@/lib/types";

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

  const a = summary.data?.data;
  const ccy = a?.base_currency ?? "USD";

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">סקירה כללית</h1>
        <SourceBadge
          source={summary.data?.source}
          stale={summary.data?.stale}
          asOf={summary.data?.as_of}
        />
      </div>

      {summary.isLoading ? (
        <div className="h-40 animate-pulse rounded-md bg-subtle" />
      ) : !a ? (
        <Panel>
          <div className="py-8 text-center">
            <p className="text-[13.5px] font-medium">אין עדיין נתוני חשבון</p>
            <p className="mx-auto mt-1 max-w-md text-[12.5px] text-muted">
              כשה־IB Gateway יהיה מחובר, שווי החשבון, היתרות והפוזיציות יופיעו כאן
              ויתעדכנו בזמן אמת. ראו RUNBOOK — סעיף 5.
            </p>
          </div>
        </Panel>
      ) : (
        <>
          <Panel title="שווי ונזילות">
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
              <Stat
                label="שווי חשבון (NLV)"
                value={a.net_liquidation}
                currency={ccy}
                title="Net Liquidation Value — שווי כל הנכסים והמזומן, במטבע הבסיס. מקור: IBKR."
              />
              <Stat label="מזומן כולל" value={a.total_cash} currency={ccy} />
              <Stat label="שווי פוזיציות" value={a.gross_position_value} currency={ccy} />
              <Stat label="כוח קנייה" value={a.buying_power} currency={ccy} />
              <Stat label="Available Funds" value={a.available_funds} currency={ccy} />
              <Stat label="Excess Liquidity" value={a.excess_liquidity} currency={ccy} />
            </div>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="רווח והפסד">
              <div className="grid grid-cols-3 gap-x-6 gap-y-4">
                <Stat label="P&L יומי" value={a.daily_pnl} currency={ccy} signed />
                <Stat label="לא ממומש" value={a.unrealized_pnl} currency={ccy} signed />
                <Stat label="ממומש (היום)" value={a.realized_pnl} currency={ccy} signed />
              </div>
              <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
                P&L יומי ולא־ממומש מגיעים ישירות מ־IBKR. תשואות תקופתיות (שבוע/חודש/שנה)
                יחושבו ממנוע הביצועים לאחר הסנכרון ההיסטורי (שלבים 5–6).
              </p>
            </Panel>

            <Panel title="מרג'ין ומטבעות">
              <div className="grid grid-cols-3 gap-x-6 gap-y-4">
                <Stat label="Initial Margin" value={a.init_margin} currency={ccy} />
                <Stat label="Maintenance Margin" value={a.maint_margin} currency={ccy} />
                <Stat label="מינוף" value={a.leverage} />
              </div>
              {balances.data && balances.data.balances.length > 0 && (
                <table className="mt-3 w-full text-[12px]">
                  <thead>
                    <tr className="text-[10.5px] text-faint">
                      <th className="pb-1 text-start font-normal">מטבע</th>
                      <th className="pb-1 text-end font-normal">מזומן</th>
                      <th className="pb-1 text-end font-normal">שער לבסיס</th>
                    </tr>
                  </thead>
                  <tbody>
                    {balances.data.balances.map((b) => (
                      <tr key={b.currency} className="border-t border-line">
                        <td className="py-1"><span className="sym">{b.currency}</span></td>
                        <td className="py-1 text-end">
                          <NumCell value={b.cash_balance} />
                        </td>
                        <td className="py-1 text-end">
                          <NumCell value={b.fx_rate_to_base} dim />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </div>

          <Panel
            title="פוזיציות פתוחות"
            actions={
              <SourceBadge
                source={positions.data?.source}
                stale={positions.data?.stale}
              />
            }
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

function NumCell({ value, dim }: { value: string | null; dim?: boolean }) {
  if (value == null) return <span className="num text-faint">—</span>;
  return (
    <span className={`num ${dim ? "text-faint" : ""}`}>
      {Number(value).toLocaleString("en-US", { maximumFractionDigits: 4 })}
    </span>
  );
}
