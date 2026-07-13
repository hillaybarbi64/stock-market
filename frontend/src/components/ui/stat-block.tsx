"use client";

/*
  StatBlock — composed metric with a clear hierarchy (UI_SYSTEM §1): a quiet
  label (optionally with an explain-me info), a prominent primary value, and
  an optional signed delta + secondary line. This is the fix for the flat
  "row of equal-weight KPIs" problem: one `primary` block anchors a screen,
  the rest are secondary.
*/

import { Num } from "@/components/ui/num";
import { MetricInfo, type MetricMeta } from "@/components/ui/metric-info";

export function StatBlock({
  label,
  value,
  kind = "money",
  currency,
  asPct,
  signed,
  flash,
  primary,
  delta,
  deltaPct,
  sub,
  meta,
  align = "start",
}: {
  label: string;
  value: string | number | null | undefined;
  kind?: "money" | "price" | "qty" | "pct";
  currency?: string;
  asPct?: boolean;
  signed?: boolean;
  flash?: boolean;
  /** render the value at display size — use for the single hero metric */
  primary?: boolean;
  /** signed change shown under the value (money) */
  delta?: string | number | null;
  /** signed change shown as percent under the value */
  deltaPct?: string | number | null;
  sub?: React.ReactNode;
  meta?: MetricMeta;
  align?: "start" | "end";
}) {
  const hasDelta = delta !== undefined || deltaPct !== undefined;
  return (
    <div className={`min-w-0 ${align === "end" ? "text-end" : ""}`}>
      <div className="flex items-center gap-1.5" style={{ justifyContent: align === "end" ? "flex-end" : "flex-start" }}>
        <span className="t-label truncate">{label}</span>
        {meta && <MetricInfo label={label} meta={meta} />}
      </div>
      <div className={`mt-1 ${primary ? "t-display" : "t-metric"}`}>
        <Num value={value} kind={kind} currency={currency} asPct={asPct} signed={signed} flash={flash} />
      </div>
      {hasDelta && (
        <div className="mt-0.5 flex items-center gap-2" style={{ justifyContent: align === "end" ? "flex-end" : "flex-start" }}>
          {delta !== undefined && <span className="text-[12px]"><Num value={delta} currency={currency} signed /></span>}
          {deltaPct !== undefined && <span className="text-[12px]"><Num value={deltaPct} asPct signed /></span>}
        </div>
      )}
      {sub ? <div className="t-help mt-0.5">{sub}</div> : null}
    </div>
  );
}
