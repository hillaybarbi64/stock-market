"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Bar } from "@/components/charts/candlestick-chart";
import { PositionsTable } from "@/components/positions/positions-table";
import { Panel } from "@/components/ui/panel";
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

  const nlv = summary.data?.data?.net_liquidation
    ? Number(summary.data.data.net_liquidation)
    : null;

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
    <div className="space-y-3.5">
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
