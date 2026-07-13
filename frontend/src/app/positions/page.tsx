"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Bar } from "@/components/charts/candlestick-chart";
import { PositionsTable } from "@/components/positions/positions-table";
import { Panel } from "@/components/ui/panel";
import { StatRail, StatCell } from "@/components/ui/stat-rail";
import { Num, Sym } from "@/components/ui/num";
import { SourceBadge } from "@/components/ui/source-badge";
import { apiGet } from "@/lib/api";
import type { AccountSummary, PositionsResponse, Sourced } from "@/lib/types";

interface BarsResponse {
  available: boolean;
  series: Record<string, { symbol: string; name: string | null; bars: Bar[] }>;
}

export default function PositionsPage() {
  const positions = useQuery({
    queryKey: ["positions"],
    queryFn: () => apiGet<PositionsResponse>("/positions"),
    refetchInterval: 30_000,
  });
  const summary = useQuery({
    queryKey: ["account", "summary"],
    queryFn: () => apiGet<Sourced<AccountSummary>>("/account/summary"),
    refetchInterval: 60_000,
  });
  const bars = useQuery({
    queryKey: ["positions", "bars"],
    queryFn: () => apiGet<BarsResponse>("/positions/bars?days=180"),
    refetchInterval: 300_000,
  });

  const a = summary.data?.data;
  const nlv = a?.net_liquidation ? Number(a.net_liquidation) : null;
  const posRows = useMemo(() => positions.data?.positions ?? [], [positions.data]);

  const top = useMemo(
    () =>
      posRows
        .filter((p) => Number(p.market_value ?? 0) > 0)
        .sort((x, y) => Number(y.market_value ?? 0) - Number(x.market_value ?? 0))[0],
    [posRows],
  );
  const topWeight =
    top && nlv ? Number(top.market_value ?? 0) / nlv : null;
  const unrealTotal = posRows.reduce((s, p) => s + Number(p.unrealized_pnl ?? 0), 0);

  const sparklines = useMemo(() => {
    const map: Record<number, number[]> = {};
    const series = bars.data?.series;
    if (series) {
      for (const [conid, s] of Object.entries(series)) {
        if (s.bars.length > 1) map[Number(conid)] = s.bars.slice(-30).map((b) => b.close);
      }
    }
    return map;
  }, [bars.data]);

  return (
    <div className="space-y-3">
      <Panel title="סקירת חשיפה" subtitle="Exposure" padding="none" grip={false}>
        <StatRail cols="grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
          <StatCell label="פוזיציות" en="Holdings">
            <span className="num">{posRows.length}</span>
          </StatCell>
          <StatCell label="שווי פוזיציות" en="Gross">
            <Num value={a?.gross_position_value} />
          </StatCell>
          <StatCell label="מזומן" en="Cash">
            <Num value={a?.total_cash} />
          </StatCell>
          <StatCell label="מינוף" en="Leverage">
            {a?.leverage != null ? <span className="num">{Number(a.leverage).toFixed(2)}×</span> : <span className="text-faint">—</span>}
          </StatCell>
          <StatCell label="P&L לא ממומש" en="Unrealized">
            <Num value={unrealTotal} signed />
          </StatCell>
          <StatCell label="החזקה מובילה" en="Top">
            {top ? (
              <span className="flex items-baseline gap-1.5">
                <Sym className="text-[13px]">{top.instrument.symbol}</Sym>
                {topWeight != null && <span className="text-[11px] font-normal text-faint"><Num value={topWeight} asPct /></span>}
              </span>
            ) : (
              <span className="text-faint">—</span>
            )}
          </StatCell>
        </StatRail>
      </Panel>

      <Panel
        title="פוזיציות פתוחות"
        actions={
          <div className="flex items-center gap-3 text-[11px] text-faint">
            {positions.data && <span>{positions.data.positions?.length ?? 0} פוזיציות</span>}
            <SourceBadge source={positions.data?.source} stale={positions.data?.stale} />
          </div>
        }
      >
        {positions.isLoading ? (
          <div className="h-32 rounded-lg skeleton" />
        ) : (
          <PositionsTable
            positions={positions.data?.positions ?? []}
            nlv={nlv}
            sparklines={sparklines}
          />
        )}
      </Panel>
      <p className="text-[11px] leading-relaxed text-faint">
        עמודות נוספות (סקטור, ימי החזקה, דיבידנדים, עמלות, MAE/MFE) יתווספו לאחר
        הסנכרון ההיסטורי — שלבים 5–7. משקל בתיק מחושב מ־NLV הנוכחי.
      </p>
    </div>
  );
}
