"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import {
  apiGet,
  apiPost,
  apiPut,
  confirmAccountBinding,
  fetchConnection,
  postReconnect,
} from "@/lib/api";

interface FlexConfig {
  configured: boolean;
  query_id: string;
  token_hint: string;
  autosync_enabled: boolean;
}

interface SyncStatus {
  configured: boolean;
  running: boolean;
  account_bound: boolean;
  cooldown: {
    active: boolean;
    until: string | null;
    remaining_seconds: number;
  };
  totals: {
    executions: number;
    cash_transactions: number;
    equity_days_from: string | null;
    equity_days_to: string | null;
  };
}

export default function ConnectAccountPage() {
  const queryClient = useQueryClient();
  const connection = useQuery({
    queryKey: ["connection"],
    queryFn: fetchConnection,
    refetchInterval: 5_000,
  });
  const flexConfig = useQuery({
    queryKey: ["sync", "flex-config"],
    queryFn: () => apiGet<FlexConfig>("/sync/flex-config"),
  });
  const sync = useQuery({
    queryKey: ["sync", "status"],
    queryFn: () => apiGet<SyncStatus>("/sync/status"),
    refetchInterval: (query) => (query.state.data?.running ? 2_000 : 15_000),
  });

  const [token, setToken] = useState("");
  const [queryId, setQueryId] = useState<string | null>(null);
  const effectiveQueryId = queryId ?? flexConfig.data?.query_id ?? "";

  const reconnect = useMutation({
    mutationFn: postReconnect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connection"] }),
  });
  const confirmBinding = useMutation({
    mutationFn: confirmAccountBinding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connection"] });
      queryClient.invalidateQueries({ queryKey: ["sync"] });
    },
  });
  const saveFlex = useMutation({
    mutationFn: () =>
      apiPut<{ ok: boolean; detail: string }>("/sync/flex-config", {
        token,
        query_id: effectiveQueryId,
        run_sync_now: false,
      }),
    onSuccess: () => {
      setToken("");
      queryClient.invalidateQueries({ queryKey: ["sync"] });
    },
  });
  const runSync = useMutation({
    mutationFn: () => apiPost<{ started: boolean; detail?: string }>("/sync/run"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sync"] }),
  });

  const connected = connection.data?.state === "connected";
  const flexReady = Boolean(flexConfig.data?.configured);
  const hasHistory = Boolean(
    sync.data &&
      (sync.data.totals.executions > 0 || sync.data.totals.equity_days_from),
  );

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <p className="sym text-[10px] tracking-[0.16em] text-accent">ACCOUNT ONBOARDING</p>
        <h1 className="mt-1 text-[19px] font-semibold tracking-tight">
          חיבור חשבון Interactive Brokers
        </h1>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-muted">
          האפליקציה אינה מבקשת ואינה שומרת את שם המשתמש, הסיסמה או קוד ה־2FA שלך.
          הכניסה מתבצעת רק בתוכנת IB Gateway הרשמית; מכאן מתקבל חיבור קריאה בלבד לנתוני
          התיק.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <StatusCard step="1" title="IB Gateway" complete={connected} />
        <StatusCard step="2" title="Flex היסטורי" complete={flexReady} />
        <StatusCard step="3" title="סנכרון ראשון" complete={hasHistory} />
      </div>

      <Panel
        title="1 · התחברות חיה דרך IB Gateway"
        subtitle={
          connection.data?.account_mode === "paper"
            ? "Paper · API port 4002"
            : "Live · API port 4001"
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_270px]">
          <ol className="space-y-2 text-[12.5px] leading-relaxed text-muted">
            <li>
              <strong className="text-fg">א.</strong> התקן ופתח את{" "}
              <a
                href="https://www.interactivebrokers.com/en/trading/ibgateway-latest.php?menu=A"
                target="_blank"
                rel="noreferrer"
                className="text-accent underline-offset-2 hover:underline"
              >
                IB Gateway הרשמי
              </a>
              .
            </li>
            <li>
              <strong className="text-fg">ב.</strong> התחבר שם לחשבון שלך ואשר 2FA. אל
              תקליד את הסיסמה בדשבורד הזה.
            </li>
            <li>
              <strong className="text-fg">ג.</strong> בהגדרות API של Gateway סמן
              <span className="mx-1 font-medium text-fg">Read-Only API</span>
              וודא שהפורט הוא{" "}
              <span className="num text-fg">{connection.data?.gateway_port ?? 4001}</span>.
            </li>
          </ol>

          <div className="rounded-sm border border-line bg-subtle p-3">
            <div className="flex items-center gap-2">
              <span
                className={`size-2 rounded-full ${connected ? "bg-gain" : "bg-warn"}`}
                aria-hidden
              />
              <strong className={connected ? "text-gain" : "text-warn"}>
                {connected ? "החשבון מחובר" : "ממתין ל־Gateway"}
              </strong>
            </div>
            <p className="mt-2 text-[11.5px] text-muted">
              {connection.data?.account_binding_confirmation_required
                ? `נמצאו נתונים קיימים. אשר רק אם הם שייכים לחשבון ${
                    connection.data?.account ?? "המוצג"
                  }.`
                : connected
                ? `חשבון ${connection.data?.account ?? "מחובר"} · מצב האפליקציה: קריאה בלבד`
                : connection.data?.last_error ??
                  "פתח את IB Gateway והשלם כניסה; הזיהוי מתבצע אוטומטית."}
            </p>
            {connection.data?.account_binding_confirmation_required ? (
              <>
                <p className="mt-2 text-[10.5px] leading-relaxed text-warn">
                  אישור חשבון שגוי יערבב נתונים. אם המספר הממוסך אינו החשבון של הנתונים
                  הקיימים, התחבר מחדש ב־Gateway ואל תאשר.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    const confirmationId =
                      connection.data?.account_binding_confirmation_id;
                    if (confirmationId) confirmBinding.mutate(confirmationId);
                  }}
                  disabled={
                    confirmBinding.isPending ||
                    !connection.data?.account_binding_confirmation_id
                  }
                  className="mt-3 rounded-sm border border-warn/40 bg-warn/10 px-3 py-1.5 text-[12px] text-warn hover:bg-warn/15 disabled:opacity-40"
                >
                  {confirmBinding.isPending ? "מאשר…" : "אשר קישור לחשבון המוצג"}
                </button>
              </>
            ) : !connected ? (
              <button
                type="button"
                onClick={() => reconnect.mutate()}
                disabled={reconnect.isPending}
                className="mt-3 rounded-sm border border-line bg-panel px-3 py-1.5 text-[12px] hover:bg-hover disabled:opacity-40"
              >
                {reconnect.isPending ? "בודק…" : "בדוק חיבור עכשיו"}
              </button>
            ) : null}
            {confirmBinding.data?.detail && (
              <p className="mt-2 text-[11px] text-muted">{confirmBinding.data.detail}</p>
            )}
          </div>
        </div>
      </Panel>

      <Panel title="2 · חיבור היסטוריה דרך Flex" subtitle="Activity Flex Query">
        <p className="mb-3 text-[12px] leading-relaxed text-muted">
          Flex מוסיף עסקאות עבר ועקומת NAV. צור ב־Client Portal טוקן ו־Activity Flex
          Query עבור חשבון אחד בלבד. השמירה אינה מפעילה סנכרון אוטומטי.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-[11px] text-faint">
            Flex Token
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder={
                flexConfig.data?.token_hint
                  ? `מוגדר (${flexConfig.data.token_hint})`
                  : "הדבק Token"
              }
              className="sym mt-1 block w-64 rounded-sm border border-line bg-bg px-2 py-1.5 text-[12px] outline-none focus:border-line-strong"
              dir="ltr"
            />
          </label>
          <label className="block text-[11px] text-faint">
            Query ID
            <input
              value={effectiveQueryId}
              onChange={(event) => setQueryId(event.target.value.trim())}
              placeholder="123456"
              className="num mt-1 block w-36 rounded-sm border border-line bg-bg px-2 py-1.5 text-[12px] outline-none focus:border-line-strong"
              dir="ltr"
            />
          </label>
          <button
            type="button"
            disabled={!token || !effectiveQueryId || saveFlex.isPending}
            onClick={() => saveFlex.mutate()}
            className="rounded-sm bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-40"
          >
            {saveFlex.isPending ? "שומר…" : "שמור פרטים בלבד"}
          </button>
        </div>
        {flexReady && (
          <p className="mt-2 text-[11.5px] text-gain">
            Flex מוגדר · Query{" "}
            <span className="num" dir="ltr">
              {flexConfig.data?.query_id}
            </span>{" "}
            · תזמון אוטומטי{" "}
            {flexConfig.data?.autosync_enabled ? "פעיל" : "כבוי לבטיחות"}
          </p>
        )}
        {saveFlex.data?.detail && (
          <p className="mt-2 text-[11.5px] text-muted">{saveFlex.data.detail}</p>
        )}
      </Panel>

      <Panel title="3 · סנכרון ראשון מבוקר">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[12.5px] text-muted">
              {hasHistory
                ? `היסטוריה נקלטה · ${sync.data?.totals.executions.toLocaleString("he-IL")} עסקאות`
                : "לאחר שמירת Flex, לחץ פעם אחת והמתן לסיום."}
            </p>
            {sync.data?.cooldown.active && sync.data.cooldown.until && (
              <p className="mt-1 text-[11.5px] text-warn">
                IBKR נמצאת בהמתנה בטוחה עד{" "}
                <span className="num" dir="ltr">
                  {new Date(sync.data.cooldown.until).toLocaleString("he-IL")}
                </span>
                . לא תישלח בקשה לפני כן.
              </p>
            )}
            {runSync.data?.detail && (
              <p className="mt-1 text-[11.5px] text-muted">{runSync.data.detail}</p>
            )}
          </div>
          <button
            type="button"
            disabled={
              !flexReady ||
              !sync.data?.account_bound ||
              sync.data?.running ||
              sync.data?.cooldown.active ||
              runSync.isPending
            }
            onClick={() => runSync.mutate()}
            className="rounded-sm border border-line bg-panel px-3 py-1.5 text-[12px] font-medium hover:bg-hover disabled:opacity-40"
          >
            {!sync.data?.account_bound
              ? "חבר Gateway תחילה"
              : sync.data?.running
                ? "הסנכרון רץ…"
                : "הרץ סנכרון ראשון"}
          </button>
        </div>
      </Panel>
    </div>
  );
}

function StatusCard({
  step,
  title,
  complete,
}: {
  step: string;
  title: string;
  complete: boolean;
}) {
  return (
    <div className="rounded-sm border border-line bg-panel px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span
          className={`num grid size-5 place-items-center rounded-full text-[10px] ${
            complete ? "bg-accent text-accent-fg" : "bg-subtle text-faint"
          }`}
        >
          {complete ? "✓" : step}
        </span>
        <span className={complete ? "text-gain" : "text-muted"}>{title}</span>
      </div>
    </div>
  );
}
