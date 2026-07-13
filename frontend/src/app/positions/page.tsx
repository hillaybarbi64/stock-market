"use client";

import { useQuery } from "@tanstack/react-query";
import { PositionsTable } from "@/components/positions/positions-table";
import { Panel } from "@/components/ui/panel";
import { SourceBadge } from "@/components/ui/source-badge";
import { apiGet } from "@/lib/api";
import type { AccountSummary, PositionsResponse, Sourced } from "@/lib/types";

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

  const nlv = summary.data?.data?.net_liquidation
    ? Number(summary.data.data.net_liquidation)
    : null;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">פוזיציות</h1>
        <SourceBadge source={positions.data?.source} stale={positions.data?.stale} />
      </div>
      <Panel>
        {positions.isLoading ? (
          <div className="h-32 animate-pulse rounded-sm bg-subtle" />
        ) : (
          <PositionsTable positions={positions.data?.positions ?? []} nlv={nlv} />
        )}
      </Panel>
      <p className="text-[11px] leading-relaxed text-faint">
        עמודות נוספות (סקטור, ימי החזקה, דיבידנדים, עמלות, MAE/MFE) יתווספו לאחר
        הסנכרון ההיסטורי — שלבים 5–7. משקל בתיק מחושב מ־NLV הנוכחי.
      </p>
    </div>
  );
}
