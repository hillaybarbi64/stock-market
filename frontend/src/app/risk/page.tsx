"use client";

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/ui/panel";
import { Num, Sym } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

interface RiskSummary {
  available: boolean;
  detail?: string;
  stale?: boolean;
  exposure?: {
    base_currency: string;
    nlv: number;
    gross_exposure: number;
    net_exposure: number;
    long_exposure: number;
    short_exposure: number;
    gross_leverage: number | null;
    cash_pct: number | null;
    margin_utilization: number | null;
    positions: {
      symbol: string;
      market_value: number;
      weight: number;
      direction: string;
      currency: string;
      sector: string | null;
    }[];
    top5_concentration: number | null;
    top10_concentration: number | null;
    currency_exposure: Record<string, number>;
    sector_exposure: Record<string, number>;
    unclassified_value: number;
  };
  scenarios?: {
    name: string;
    assumptions: string;
    impact_base: number;
    impact_pct_nlv: number | null;
    nlv_after: number;
  }[];
  notes?: string[];
}

export default function RiskPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["risk", "summary"],
    queryFn: () => apiGet<RiskSummary>("/risk/summary"),
    refetchInterval: 60_000,
  });

  if (isLoading) return <div className="mx-auto h-60 max-w-6xl animate-pulse rounded-md bg-subtle" />;

  if (isError || !data?.available || !data.exposure) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-[17px] font-semibold tracking-tight">סיכונים</h1>
        <Panel>
          <p className="py-10 text-center text-[12.5px] text-muted">
            {isError
              ? "שגיאה בקבלת נתוני הסיכון מה-Backend."
              : data?.detail ??
                "ניתוח הסיכונים דורש נתוני חשבון חיים — חבר את IB Gateway (ראו RUNBOOK)."}
          </p>
        </Panel>
      </div>
    );
  }

  const e = data.exposure;
  const ccy = e.base_currency;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">סיכונים</h1>
        {data.stale && (
          <span className="sym rounded-sm bg-subtle px-1.5 py-px text-[9.5px] text-warn">
            LAST KNOWN · STALE
          </span>
        )}
      </div>

      <Panel title="חשיפה">
        <div className="grid grid-cols-3 gap-x-6 gap-y-4 sm:grid-cols-4 lg:grid-cols-8">
          <S label="ברוטו" v={e.gross_exposure} ccy={ccy} />
          <S label="נטו" v={e.net_exposure} ccy={ccy} />
          <S label="Long" v={e.long_exposure} ccy={ccy} />
          <S label="Short" v={e.short_exposure} ccy={ccy} />
          <SP label="מינוף ברוטו" v={e.gross_leverage} x />
          <SP label="מזומן מהתיק" v={e.cash_pct} />
          <SP label="ניצול מרג'ין" v={e.margin_utilization} />
          <SP label="ריכוזיות Top-5" v={e.top5_concentration} />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="משקלי פוזיציות">
          {e.positions.length ? (
            <ul className="space-y-1.5">
              {e.positions.map((p) => (
                <li key={p.symbol} className="flex items-center gap-3 text-[12.5px]">
                  <span className="w-14 shrink-0"><Sym>{p.symbol}</Sym></span>
                  <div className="h-3 flex-1 rounded-sm bg-subtle" dir="ltr">
                    <div
                      className={`h-full rounded-sm ${p.direction === "SHORT" ? "bg-loss/60" : "bg-accent/60"}`}
                      style={{ width: `${Math.min(100, p.weight * 100)}%` }}
                    />
                  </div>
                  <span className="w-14 text-end"><Num value={p.weight} asPct /></span>
                  <span className="w-24 text-end"><Num value={p.market_value} currency={p.currency} /></span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-[12.5px] text-muted">אין פוזיציות פתוחות.</p>
          )}
        </Panel>

        <Panel title="חשיפת מטבע וסקטור">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h3 className="mb-1.5 text-[11px] text-faint">מטבע (פוזיציות + מזומן זר)</h3>
              {Object.entries(e.currency_exposure).map(([k, v]) => (
                <div key={k} className="flex justify-between border-t border-line py-1 text-[12.5px]">
                  <Sym>{k}</Sym>
                  <Num value={v} />
                </div>
              ))}
            </div>
            <div>
              <h3 className="mb-1.5 text-[11px] text-faint">סקטור</h3>
              {Object.entries(e.sector_exposure).map(([k, v]) => (
                <div key={k} className="flex justify-between border-t border-line py-1 text-[12.5px]">
                  <span>{k}</span>
                  <Num value={v} />
                </div>
              ))}
              {e.unclassified_value > 0 && (
                <div className="flex justify-between border-t border-line py-1 text-[12.5px] text-muted">
                  <span>לא מסווג עדיין</span>
                  <Num value={e.unclassified_value} />
                </div>
              )}
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="תרחישי קיצון — חישוב פרמטרי, לא תחזית">
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="text-[10.5px] text-faint">
              <th className="pb-1.5 text-start font-normal">תרחיש</th>
              <th className="pb-1.5 text-end font-normal">השפעה ({ccy})</th>
              <th className="pb-1.5 text-end font-normal">% מהתיק</th>
              <th className="pb-1.5 text-end font-normal">NLV לאחר</th>
            </tr>
          </thead>
          <tbody>
            {data.scenarios?.map((s) => (
              <tr key={s.name} className="border-t border-line align-top hover:bg-hover" title={s.assumptions}>
                <td className="py-1.5 pe-4">
                  {s.name}
                  <div className="mt-0.5 text-[10.5px] leading-snug text-faint">{s.assumptions}</div>
                </td>
                <td className="py-1.5 text-end"><Num value={s.impact_base} signed /></td>
                <td className="py-1.5 text-end"><Num value={s.impact_pct_nlv} asPct signed /></td>
                <td className="py-1.5 text-end"><Num value={s.nlv_after} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {data.notes && (
        <ul className="space-y-1 text-[10.5px] text-faint">
          {data.notes.map((n) => (
            <li key={n}>• {n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function S({ label, v, ccy }: { label: string; v: number; ccy: string }) {
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[15px] font-semibold"><Num value={v} currency={ccy} /></div>
    </div>
  );
}

function SP({ label, v, x }: { label: string; v: number | null; x?: boolean }) {
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[15px] font-semibold">
        {v == null ? (
          <span className="text-faint">—</span>
        ) : x ? (
          <span className="num">{v.toFixed(2)}×</span>
        ) : (
          <Num value={v} asPct />
        )}
      </div>
    </div>
  );
}
