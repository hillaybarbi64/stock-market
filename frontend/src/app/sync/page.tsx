"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Panel } from "@/components/ui/panel";
import { apiGet, apiPost } from "@/lib/api";

interface SyncRunRow {
  id: number;
  kind: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "failed" | "partial";
  date_range_from: string | null;
  date_range_to: string | null;
  records_upserted: number;
  records_skipped: number;
  errors: Record<string, unknown> | null;
}

interface SyncStatus {
  configured: boolean;
  running: boolean;
  totals: {
    executions: number;
    cash_transactions: number;
    equity_days_from: string | null;
    equity_days_to: string | null;
  };
  runs: SyncRunRow[];
}

interface ReconCheck {
  name: string;
  status: string;
  note?: string;
  [key: string]: unknown;
}

export default function SyncPage() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["sync", "status"],
    queryFn: () => apiGet<SyncStatus>("/sync/status"),
    refetchInterval: (q) => (q.state.data?.running ? 2_000 : 15_000),
  });
  const recon = useQuery({
    queryKey: ["sync", "reconciliation"],
    queryFn: () => apiGet<{ checks: ReconCheck[] }>("/sync/reconciliation"),
    refetchInterval: 60_000,
  });
  const runSync = useMutation({
    mutationFn: () => apiPost<{ started: boolean; detail?: string }>("/sync/run"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sync"] }),
  });

  const s = status.data;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">סנכרון</h1>
        <button
          type="button"
          onClick={() => runSync.mutate()}
          disabled={!s?.configured || s?.running || runSync.isPending}
          className="rounded-sm bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {s?.running ? "סנכרון רץ…" : "הרץ סנכרון עכשיו"}
        </button>
      </div>

      {s && !s.configured && (
        <Panel>
          <p className="text-[13px] font-medium text-warn">Flex Web Service אינו מוגדר</p>
          <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
            כדי לסנכרן את כל ההיסטוריה (עסקאות, דיבידנדים, עמלות, הפקדות, NAV יומי) יש
            להגדיר Flex Query וטוקן בפורטל של IBKR ולהזין{" "}
            <span className="sym">IBKR_FLEX_TOKEN</span> ו־
            <span className="sym">IBKR_FLEX_QUERY_ID</span> בקובץ .env — הוראות מלאות
            ב־RUNBOOK סעיף 3.
          </p>
        </Panel>
      )}

      {runSync.data && !runSync.data.started && (
        <p className="rounded-sm bg-subtle px-3 py-2 text-[12px] text-warn">
          {runSync.data.detail}
        </p>
      )}

      <Panel title="נתונים מסונכרנים">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13px] sm:grid-cols-4">
          <Metric label="ביצועים (Executions)" value={s?.totals.executions} />
          <Metric label="תנועות מזומן" value={s?.totals.cash_transactions} />
          <div>
            <dt className="text-[11px] text-faint">טווח NAV יומי</dt>
            <dd className="num mt-0.5 text-[12.5px]">
              {s?.totals.equity_days_from
                ? `${s.totals.equity_days_from} → ${s.totals.equity_days_to}`
                : "—"}
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel title="בדיקות התאמה (Reconciliation)">
        {recon.data?.checks.length ? (
          <ul className="space-y-2">
            {recon.data.checks.map((c) => (
              <li key={c.name} className="flex items-start gap-2 text-[12.5px]">
                <span
                  className={`mt-1 size-1.5 shrink-0 rounded-full ${
                    c.status === "ok"
                      ? "bg-gain"
                      : c.status === "mismatch"
                        ? "bg-loss"
                        : "bg-faint"
                  }`}
                  aria-hidden
                />
                <div>
                  <span className="sym text-[11.5px]">{c.name}</span>
                  <span className="ms-2 text-muted">{c.note}</span>
                  {c.status === "mismatch" && (
                    <pre className="num mt-1 rounded-sm bg-subtle p-2 text-[10.5px]" dir="ltr">
                      {JSON.stringify(c, null, 1)}
                    </pre>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12.5px] text-muted">טוען בדיקות…</p>
        )}
      </Panel>

      <Panel title="ריצות אחרונות">
        {s?.runs.length ? (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-[10.5px] text-faint">
                <th className="pb-1.5 text-start font-normal">התחלה</th>
                <th className="pb-1.5 text-start font-normal">סטטוס</th>
                <th className="pb-1.5 text-start font-normal">טווח</th>
                <th className="pb-1.5 text-end font-normal">עודכנו</th>
                <th className="pb-1.5 text-end font-normal">ללא שינוי</th>
                <th className="pb-1.5 text-start font-normal">הערות</th>
              </tr>
            </thead>
            <tbody>
              {s.runs.map((r) => (
                <tr key={r.id} className="border-t border-line">
                  <td className="num py-1.5">{new Date(r.started_at).toLocaleString("he-IL")}</td>
                  <td className="py-1.5">
                    <span
                      className={`sym rounded-sm px-1.5 py-px text-[9.5px] ${
                        r.status === "ok"
                          ? "bg-subtle text-gain"
                          : r.status === "failed"
                            ? "bg-subtle text-loss"
                            : "bg-subtle text-muted"
                      }`}
                    >
                      {r.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="num py-1.5 text-[11px]">
                    {r.date_range_from ? `${r.date_range_from} → ${r.date_range_to}` : "—"}
                  </td>
                  <td className="num py-1.5 text-end">{r.records_upserted}</td>
                  <td className="num py-1.5 text-end">{r.records_skipped}</td>
                  <td className="py-1.5 text-[11px] text-faint" dir="ltr">
                    {r.errors && "error" in r.errors ? String(r.errors.error) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="py-4 text-center text-[12.5px] text-muted">
            טרם בוצע סנכרון. לאחר הגדרת Flex, הריצה הראשונה תמשוך את כל ההיסטוריה מאז
            פתיחת החשבון.
          </p>
        )}
      </Panel>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div>
      <dt className="text-[11px] text-faint">{label}</dt>
      <dd className="num mt-0.5 text-[15px] font-semibold">
        {value?.toLocaleString("en-US") ?? "—"}
      </dd>
    </div>
  );
}
