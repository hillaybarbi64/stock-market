"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Num } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Rule {
  id: number;
  name: string;
  metric: string;
  operator: string;
  threshold: number;
  enabled: boolean;
}

interface AlertEventRow {
  id: number;
  rule: string;
  fired_at: string;
  value: number;
  message: string;
}

const OPERATORS = [
  ["gt", "גדול מ-"],
  ["gte", "גדול/שווה"],
  ["lt", "קטן מ-"],
  ["lte", "קטן/שווה"],
];

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const metrics = useQuery({
    queryKey: ["alerts", "metrics"],
    queryFn: () => apiGet<{ metrics: Record<string, string> }>("/alerts/metrics"),
  });
  const rules = useQuery({
    queryKey: ["alerts", "rules"],
    queryFn: () => apiGet<{ rules: Rule[] }>("/alerts/rules"),
  });
  const events = useQuery({
    queryKey: ["alerts", "events"],
    queryFn: () => apiGet<{ events: AlertEventRow[] }>("/alerts/events"),
    refetchInterval: 30_000,
  });

  const [form, setForm] = useState({ name: "", metric: "daily_loss_pct", operator: "gt", threshold: "" });

  const createRule = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_URL}/api/alerts/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, threshold: Number(form.threshold) }),
      });
      if (!res.ok) throw new Error(String(res.status));
    },
    onSuccess: () => {
      setForm((f) => ({ ...f, name: "", threshold: "" }));
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
  const deleteRule = useMutation({
    mutationFn: (id: number) => fetch(`${API_URL}/api/alerts/rules/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-[17px] font-semibold tracking-tight">הגדרות</h1>

      <Panel title="כללי התראה">
        <div className="flex flex-wrap items-end gap-3">
          <L label="שם">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="הפסד יומי מעל 2%" className={INPUT + " w-44"} />
          </L>
          <L label="מדד">
            <select value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })} className={INPUT}>
              {Object.entries(metrics.data?.metrics ?? {}).map(([k, label]) => (
                <option key={k} value={k}>{label}</option>
              ))}
            </select>
          </L>
          <L label="תנאי">
            <select value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })} className={INPUT}>
              {OPERATORS.map(([k, label]) => (
                <option key={k} value={k}>{label}</option>
              ))}
            </select>
          </L>
          <L label="סף">
            <input dir="ltr" value={form.threshold} onChange={(e) => setForm({ ...form, threshold: e.target.value })}
              placeholder="2" className={INPUT + " num w-20"} />
          </L>
          <button type="button"
            onClick={() => createRule.mutate()}
            disabled={!form.name || !form.threshold || createRule.isPending}
            className="rounded-sm bg-accent px-3 py-1.5 text-[12px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-40">
            הוסף כלל
          </button>
        </div>

        {rules.data?.rules.length ? (
          <table className="mt-4 w-full text-[12.5px]">
            <tbody>
              {rules.data.rules.map((r) => (
                <tr key={r.id} className="border-t border-line">
                  <td className="py-1.5">{r.name}</td>
                  <td className="py-1.5 text-muted">{metrics.data?.metrics[r.metric] ?? r.metric}</td>
                  <td className="num py-1.5">{r.operator} {r.threshold}</td>
                  <td className="py-1.5 text-end">
                    <button type="button" onClick={() => deleteRule.mutate(r.id)}
                      className="text-[10.5px] text-faint hover:text-loss">מחק</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-4 text-[11.5px] text-faint">
            אין כללים עדיין. ההתראות מופיעות בתוך המערכת; שליחה ל-Email/Telegram מתוכננת כהרחבה עתידית.
          </p>
        )}
      </Panel>

      <Panel title="התראות אחרונות">
        {events.data?.events.length ? (
          <ul className="space-y-1.5">
            {events.data.events.map((e) => (
              <li key={e.id} className="flex items-baseline justify-between border-t border-line py-1 text-[12px] first:border-0">
                <span>{e.message}</span>
                <span className="num text-[10.5px] text-faint">{new Date(e.fired_at).toLocaleString("he-IL")}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-muted">לא נורו התראות.</p>
        )}
      </Panel>

      <Panel title="תצוגה ונתונים">
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[12.5px] sm:grid-cols-3">
          <div><dt className="text-[11px] text-faint">אזור זמן</dt><dd className="mt-0.5">Asia/Jerusalem (ברירת מחדל)</dd></div>
          <div><dt className="text-[11px] text-faint">מטבע תצוגה</dt><dd className="mt-0.5">מטבע הבסיס של החשבון (USD)</dd></div>
          <div><dt className="text-[11px] text-faint">מספר חשבון</dt><dd className="mt-0.5">ממוסך תמיד בממשק ובלוגים</dd></div>
          <div><dt className="text-[11px] text-faint">שיטת שיוך עסקאות</dt><dd className="mt-0.5">FIFO (תואם IBKR) + תיקון ידני</dd></div>
          <div><dt className="text-[11px] text-faint">ריבית חסרת סיכון (Sharpe)</dt><dd className="num mt-0.5"><Num value={0.04} asPct /></dd></div>
          <div><dt className="text-[11px] text-faint">מצב תצוגה</dt><dd className="mt-0.5">כהה/בהיר — בכפתור שבסרגל העליון</dd></div>
        </dl>
        <p className="mt-3 text-[10.5px] text-faint">
          עריכת ההגדרות הללו מה-UI תתווסף בשלב הליטוש; כרגע ניתן לשנותן ב-.env / קוד התצורה.
        </p>
      </Panel>
    </div>
  );
}

const INPUT = "rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none focus:border-line-strong";

function L({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-[10.5px] text-faint">
      {label}
      {children}
    </label>
  );
}
