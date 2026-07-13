"use client";

/*
  MetricInfo — the "explain me" affordance required for every meaningful
  metric (UI_SYSTEM §12). A small info trigger that reveals a structured
  card on hover AND keyboard focus (accessible), describing what the metric
  means and, crucially, its data provenance and calculation caveats.
*/

export interface MetricMeta {
  what?: string; // what it means / why it matters
  how?: string; // how it's calculated
  source?: string; // ibkr_gateway | flex | computed | market_data
  updated?: string; // ISO timestamp or human string
  currency?: string;
  includesFees?: boolean;
  includesDividends?: boolean;
  includesFlows?: boolean; // deposits/withdrawals
  live?: boolean; // live vs historical
  limits?: string;
}

const SOURCE_LABEL: Record<string, string> = {
  ibkr_gateway: "IBKR (חי)",
  ibkr_flex: "Flex (היסטורי)",
  flex: "Flex (היסטורי)",
  computed: "מחושב על ידי המערכת",
  market_data: "נתוני שוק",
  local_snapshot: "צילום מקומי",
};

function yn(v: boolean | undefined): string | null {
  if (v === undefined) return null;
  return v ? "כן" : "לא";
}

export function MetricInfo({ label, meta }: { label: string; meta: MetricMeta }) {
  const rows: [string, string | null][] = [
    ["הסבר", meta.what ?? null],
    ["חישוב", meta.how ?? null],
    ["מקור", meta.source ? (SOURCE_LABEL[meta.source] ?? meta.source) : null],
    ["עודכן", meta.updated ? new Date(meta.updated).toLocaleString("he-IL") : null],
    ["מטבע", meta.currency ?? null],
    ["כולל עמלות", yn(meta.includesFees)],
    ["כולל דיבידנדים", yn(meta.includesDividends)],
    ["כולל הפקדות/משיכות", yn(meta.includesFlows)],
    ["סוג נתון", meta.live === undefined ? null : meta.live ? "חי" : "היסטורי"],
    ["מגבלות", meta.limits ?? null],
  ];
  const visible = rows.filter(([, v]) => v);

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label={`הסבר: ${label}`}
        className="flex size-3.5 items-center justify-center rounded-full border border-line text-[9px] leading-none text-faint transition-colors hover:border-line-strong hover:text-muted focus-visible:text-fg"
        tabIndex={0}
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute top-full z-40 mt-1.5 hidden w-72 rounded-md border border-line-strong bg-panel p-3 text-start elev-overlay group-hover:block group-focus-within:block"
        style={{ insetInlineStart: 0 }}
      >
        <span className="t-h2 mb-1.5 block text-fg">{label}</span>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          {visible.map(([k, v]) => (
            <span key={k} className="contents">
              <dt className="t-help whitespace-nowrap">{k}</dt>
              <dd className="text-[11px] leading-snug text-muted">{v}</dd>
            </span>
          ))}
        </dl>
      </span>
    </span>
  );
}
