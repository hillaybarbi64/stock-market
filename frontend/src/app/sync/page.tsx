"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { apiGet, apiPost, apiPut } from "@/lib/api";

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
  last_failure: {
    code: string | null;
    error: string | null;
    help_he: string | null;
    started_at: string;
  } | null;
  autosync_enabled: boolean;
  account_bound: boolean;
  cooldown: {
    active: boolean;
    error_code: string | null;
    until: string | null;
    remaining_seconds: number;
  };
  totals: {
    executions: number;
    cash_transactions: number;
    equity_days_from: string | null;
    equity_days_to: string | null;
  };
  runs: SyncRunRow[];
}

interface FlexConfig {
  configured: boolean;
  query_id: string;
  token_hint: string;
  autosync_enabled: boolean;
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
  const flexConfig = useQuery({
    queryKey: ["sync", "flex-config"],
    queryFn: () => apiGet<FlexConfig>("/sync/flex-config"),
  });
  const recon = useQuery({
    queryKey: ["sync", "reconciliation"],
    queryFn: () => apiGet<{ checks: ReconCheck[] }>("/sync/reconciliation"),
    refetchInterval: 60_000,
  });
  const s = status.data;
  const fail = s?.last_failure;
  const isIpBlock =
    fail?.code === "1013" ||
    (typeof fail?.error === "string" && fail.error.includes("1013"));
  const outboundIp = useQuery({
    queryKey: ["sync", "outbound-ip"],
    queryFn: () => apiGet<{ ip: string | null; ok: boolean }>("/sync/outbound-ip"),
    enabled: isIpBlock,
    staleTime: 60_000,
  });
  const runSync = useMutation({
    mutationFn: () => apiPost<{ started: boolean; detail?: string }>("/sync/run"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sync"] }),
  });

  const [token, setToken] = useState("");
  const [queryId, setQueryId] = useState<string | null>(null);
  const effectiveQueryId = queryId ?? flexConfig.data?.query_id ?? "";
  const saveFlex = useMutation({
    mutationFn: ({ runSyncNow }: { runSyncNow: boolean }) =>
      apiPut<{
        ok: boolean;
        detail?: string;
        sync_started?: boolean;
      }>("/sync/flex-config", {
        token,
        query_id: effectiveQueryId,
        run_sync_now: runSyncNow,
      }),
    onSuccess: () => {
      setToken("");
      queryClient.invalidateQueries({ queryKey: ["sync"] });
      queryClient.invalidateQueries({ queryKey: ["trades"] });
    },
  });

  const flexBlocked = Boolean(s?.cooldown?.active);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">סנכרון</h1>
        <button
          type="button"
          onClick={() => runSync.mutate()}
          disabled={
            !s?.configured ||
            !s?.account_bound ||
            s?.running ||
            flexBlocked ||
            runSync.isPending
          }
          className="rounded-sm bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {s?.running
            ? "סנכרון רץ…"
            : !s?.account_bound
              ? "חבר Gateway תחילה"
              : flexBlocked
              ? `Flex בהמתנה · ${formatDuration(s?.cooldown.remaining_seconds ?? 0)}`
              : "הרץ סנכרון עכשיו"}
        </button>
      </div>

      {fail && (
        <div
          className="rounded-sm border border-[color-mix(in_srgb,var(--warn)_40%,transparent)] bg-[color-mix(in_srgb,var(--warn)_10%,transparent)] px-4 py-3"
          role="alert"
        >
          <p className="text-[13px] font-semibold text-warn">
            סנכרון נכשל{fail.code ? ` · קוד ${fail.code}` : ""}
          </p>
          {fail.error && (
            <p className="sym mt-1 text-[11.5px] text-muted" dir="ltr">
              {fail.error}
            </p>
          )}
          {fail.help_he && (
            <p className="mt-2 text-[12.5px] leading-relaxed text-fg">{fail.help_he}</p>
          )}
          {isIpBlock && (
            <div className="mt-3 space-y-1.5 text-[12.5px] leading-relaxed">
              <p>
                כתובת ה־IP הציבורית שממנה רץ הסנכרון עכשיו:{" "}
                <span className="num font-semibold" dir="ltr">
                  {outboundIp.data?.ip ?? "…טוען"}
                </span>
              </p>
              <ol className="list-decimal space-y-1 pe-5 text-muted">
                <li>היכנס ל־IBKR Client Portal</li>
                <li>Settings → Account Settings → Flex Web Service</li>
                <li>
                  הוסף את ה־IP למעלה לרשימת הכתובות המורשות (או צור Token חדש עם ה־IP הנוכחי)
                </li>
                <li>חזור לכאן → המתן ~90 שניות → לחץ «הרץ סנכרון עכשיו»</li>
              </ol>
            </div>
          )}
        </div>
      )}

      {s?.cooldown.active && s.cooldown.until && (
        <div className="rounded-sm border border-warn/30 bg-warn/5 px-3 py-2.5 text-[12px] leading-relaxed text-warn">
          <strong className="font-semibold">IBKR Flex בהמתנה בטוחה (1025).</strong>{" "}
          זו חסימה זמנית ברמת החשבון, לא תקלה בטוקן. המערכת לא תשלח בקשות נוספות עד{" "}
          <span className="num" dir="ltr">
            {new Date(s.cooldown.until).toLocaleString("he-IL")}
          </span>
          , ואז תאפשר ניסיון יחיד.
        </div>
      )}

      <Panel title="הגדרת Flex (היסטוריית עסקאות)" subtitle="Activity Flex Query">
        <p className="mb-3 text-[12.5px] leading-relaxed text-muted">
          Gateway החי מביא פוזיציות ו־P&amp;L עדכניים בלבד.{" "}
          <strong className="font-medium text-fg">עסקאות עבר</strong> מגיעות מ־Flex Web
          Service. צור Token + Activity Flex Query בפורטל IBKR (ראו RUNBOOK §3), הדבק כאן,
          ובחר במפורש אם לשמור בלבד או להתחיל ניסיון סנכרון יחיד.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-[11px] text-faint">
            Flex Token
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={
                flexConfig.data?.token_hint
                  ? `שמור (${flexConfig.data.token_hint})`
                  : "הדבק Token מהפורטל"
              }
              className="sym mt-1 block w-64 rounded-sm border border-line bg-bg px-2 py-1.5 text-[12px] outline-none focus:border-line-strong"
              dir="ltr"
            />
          </label>
          <label className="block text-[11px] text-faint">
            Query ID
            <input
              value={effectiveQueryId}
              onChange={(e) => setQueryId(e.target.value.trim())}
              placeholder="123456"
              className="num mt-1 block w-36 rounded-sm border border-line bg-bg px-2 py-1.5 text-[12px] outline-none focus:border-line-strong"
              dir="ltr"
            />
          </label>
          <button
            type="button"
            disabled={!token || !effectiveQueryId || saveFlex.isPending}
            onClick={() => saveFlex.mutate({ runSyncNow: !flexBlocked })}
            className="rounded-sm border border-line bg-panel px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-hover disabled:opacity-40"
          >
            {saveFlex.isPending
              ? "שומר…"
              : flexBlocked
                ? "שמור פרטים בלבד"
                : "שמור והפעל סנכרון"}
          </button>
        </div>
        {flexConfig.data?.configured && (
          <div className="mt-2 flex flex-wrap items-center gap-x-2 text-[11.5px]">
            <p className="text-gain">
              Flex מוגדר · Query{" "}
              <span className="num" dir="ltr">
                {flexConfig.data.query_id}
              </span>
              {flexConfig.data.token_hint ? (
                <>
                  {" "}
                  · Token{" "}
                  <span className="sym" dir="ltr">
                    {flexConfig.data.token_hint}
                  </span>
                </>
              ) : null}
            </p>
            <span className={s?.autosync_enabled ? "text-gain" : "text-warn"}>
              · תזמון יומי {s?.autosync_enabled ? "פעיל" : "כבוי לבטיחות"}
            </span>
          </div>
        )}
        {saveFlex.data?.detail && (
          <p className="mt-2 text-[12px] text-muted">{saveFlex.data.detail}</p>
        )}
        {saveFlex.isError && (
          <p className="mt-2 text-[12px] text-loss">שמירה נכשלה — בדוק את הערכים ונסה שוב.</p>
        )}
      </Panel>

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
          <div className="flex items-end">
            <Link
              href="/trades"
              className="text-[12px] text-accent underline-offset-2 hover:underline"
            >
              מעבר לבלוטר עסקאות →
            </Link>
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
                  <td className="py-1.5 text-[11px] text-faint">
                    {r.errors && "error" in r.errors ? (
                      <span dir="ltr">{String(r.errors.error)}</span>
                    ) : (
                      ""
                    )}
                    {r.errors && "help_he" in r.errors && r.errors.help_he ? (
                      <span className="mt-0.5 block text-[10.5px] text-muted">
                        {String(r.errors.help_he)}
                      </span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="py-4 text-center text-[12.5px] text-muted">
            טרם בוצע סנכרון. לאחר שמירת Flex למעלה, הריצה הראשונה תמשוך את ההיסטוריה לפי
            טווח ה־Query (בדרך כלל ~365 יום).
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

function formatDuration(totalSeconds: number): string {
  const totalMinutes = Math.ceil(Math.max(0, totalSeconds) / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")} ש׳`;
  return `${Math.max(1, minutes)} דק׳`;
}
