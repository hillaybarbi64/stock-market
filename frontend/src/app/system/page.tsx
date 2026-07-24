"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Panel } from "@/components/ui/panel";
import { fetchConnection, fetchHealth, postReconnect } from "@/lib/api";

export default function SystemPage() {
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 10_000 });
  const conn = useQuery({
    queryKey: ["connection"],
    queryFn: fetchConnection,
    refetchInterval: 5_000,
  });
  const reconnect = useMutation({
    mutationFn: postReconnect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connection"] }),
  });

  const c = conn.data;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-[17px] font-semibold tracking-tight">מצב מערכת</h1>

      <Panel title="חיבור IBKR">
        {!c ? (
          <div className="h-24 rounded-sm skeleton" />
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13px] sm:grid-cols-3">
            <Item label="מצב" value={<span className="sym">{c.state.toUpperCase()}</span>} />
            <Item
              label="הרשאה"
              value={c.readonly ? "App Read-Only · יש לאמת גם ב־Gateway" : "—"}
            />
            <Item
              label="חשבון"
              value={c.account ? <span className="sym">{c.account}</span> : "—"}
            />
            <Item
              label="מחובר מאז"
              value={c.connected_since ? new Date(c.connected_since).toLocaleString("he-IL") : "—"}
            />
            <Item
              label="עדכון אחרון"
              value={c.last_update ? new Date(c.last_update).toLocaleString("he-IL") : "—"}
            />
            <Item
              label="Market Data"
              value={
                c.market_data_type === "delayed"
                  ? "מושהה (~15 דק')"
                  : c.market_data_type ?? "לא ידוע עדיין"
              }
            />
            <Item label="ניסיונות חיבור מחדש" value={String(c.reconnect_attempts)} />
            <Item
              label="ניסיון הבא בעוד"
              value={c.next_retry_in_s != null ? `${c.next_retry_in_s} שניות` : "—"}
            />
            <div className="flex items-end">
              <button
                type="button"
                onClick={() => reconnect.mutate()}
                disabled={reconnect.isPending || c.state === "connected"}
                className="rounded-sm border border-line px-3 py-1 text-[12px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-40"
              >
                התחבר מחדש עכשיו
              </button>
            </div>
          </dl>
        )}
        {c?.last_error && (
          <p className="mt-3 rounded-sm bg-subtle px-3 py-2 text-[12px] text-warn" dir="ltr">
            {c.last_error}
          </p>
        )}
      </Panel>

      <Panel title="רכיבים">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13px] sm:grid-cols-4">
          {health.data ? (
            Object.entries(health.data.components).map(([name, comp]) => (
              <div key={name}>
                <dt className="text-[11px] text-faint"><span className="sym">{name}</span></dt>
                <dd className="mt-0.5 flex items-center gap-1.5">
                  <span
                    className={`size-1.5 rounded-full ${comp.status === "ok" ? "bg-gain" : "bg-loss"}`}
                    aria-hidden
                  />
                  {comp.status === "ok" ? "תקין" : comp.detail ?? comp.status}
                </dd>
              </div>
            ))
          ) : (
            <span className="text-muted">טוען…</span>
          )}
          {health.data && (
            <>
              <Item label="גרסה" value={<span className="num">{health.data.version}</span>} />
              <Item
                label="Uptime"
                value={
                  <span className="num">{Math.floor(health.data.uptime_seconds / 60)} min</span>
                }
              />
              <Item label="סביבה" value={<span className="sym">{health.data.environment}</span>} />
            </>
          )}
        </dl>
      </Panel>
    </div>
  );
}

function Item({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] text-faint">{label}</dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}
