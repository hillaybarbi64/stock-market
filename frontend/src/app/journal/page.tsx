"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { JournalEntryForm } from "@/components/journal/entry-form";
import { Panel } from "@/components/ui/panel";
import { Num, Sym } from "@/components/ui/num";
import { apiGet, apiPost } from "@/lib/api";

export interface CycleRow {
  id: number;
  symbol: string;
  name: string | null;
  direction: "LONG" | "SHORT";
  open_time: string;
  close_time: string | null;
  max_quantity: string;
  realized_pnl: string | null;
  fees_total: string | null;
  matching_method: string;
  holding_days: number;
  journal: {
    id: number;
    strategy: string | null;
    rating: number | null;
    followed_plan: boolean | null;
    key_lesson: string | null;
  } | null;
}

interface AnalyticsBucket {
  key: string;
  count: number;
  wins: number;
  win_rate: number | null;
  total_pnl: number;
  avg_pnl: number | null;
  total_fees: number;
  small_sample: boolean;
}

const DIMENSIONS: [string, string][] = [
  ["strategy", "אסטרטגיה"],
  ["setup", "Setup"],
  ["symbol", "סימול"],
  ["direction", "Long/Short"],
  ["weekday", "יום בשבוע"],
  ["hour", "שעת פתיחה"],
  ["emotional_state", "מצב רגשי"],
  ["followed_plan", "משמעת"],
];

export default function JournalPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<CycleRow | null>(null);
  const [dimension, setDimension] = useState("strategy");

  const cycles = useQuery({
    queryKey: ["journal", "cycles"],
    queryFn: () => apiGet<{ cycles: CycleRow[] }>("/journal/cycles"),
  });
  const analytics = useQuery({
    queryKey: ["journal", "analytics", dimension],
    queryFn: () =>
      apiGet<{ note: string; buckets: AnalyticsBucket[] }>(
        `/journal/analytics?dimension=${dimension}`,
      ),
  });
  const rebuild = useMutation({
    mutationFn: () => apiPost("/journal/cycles/rebuild"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["journal"] }),
  });

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">יומן מסחר</h1>
        <button
          type="button"
          onClick={() => rebuild.mutate()}
          disabled={rebuild.isPending}
          className="rounded-sm border border-line px-3 py-1 text-[12px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-40"
          title="בונה מחדש את שיוך הקניות/מכירות למחזורי עסקה בשיטת FIFO. שיוכים ידניים נשמרים."
        >
          {rebuild.isPending ? "בונה…" : "בנה מחזורי עסקה מחדש"}
        </button>
      </div>

      <Panel title="מחזורי עסקה (Round Trips) — שיוך FIFO אוטומטי, ניתן לתיקון">
        {cycles.isLoading ? (
          <div className="h-32 rounded-sm skeleton" />
        ) : !cycles.data?.cycles.length ? (
          <div className="py-10 text-center">
            <p className="text-[13.5px] font-medium">אין עדיין מחזורי עסקה</p>
            <p className="mx-auto mt-1 max-w-md text-[12.5px] text-muted">
              לאחר סנכרון עסקאות, לחץ על &quot;בנה מחזורי עסקה מחדש&quot; כדי לשייך
              קניות ומכירות לעסקאות שלמות.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-[10.5px] text-faint">
                  <th className="pb-1.5 text-start font-normal">נכס</th>
                  <th className="pb-1.5 text-start font-normal">כיוון</th>
                  <th className="pb-1.5 text-start font-normal">פתיחה</th>
                  <th className="pb-1.5 text-start font-normal">סגירה</th>
                  <th className="pb-1.5 text-end font-normal">ימים</th>
                  <th className="pb-1.5 text-end font-normal">כמות שיא</th>
                  <th className="pb-1.5 text-end font-normal">P&L (לפני עמלות)</th>
                  <th className="pb-1.5 text-end font-normal">עמלות</th>
                  <th className="pb-1.5 text-start font-normal">אסטרטגיה</th>
                  <th className="pb-1.5 text-start font-normal">דירוג</th>
                  <th className="pb-1.5 text-start font-normal">יומן</th>
                </tr>
              </thead>
              <tbody>
                {cycles.data.cycles.map((c) => (
                  <tr key={c.id} className="border-t border-line hover:bg-hover">
                    <td className="py-1.5"><Sym>{c.symbol}</Sym></td>
                    <td className="py-1.5">
                      <span className="sym text-[10.5px] text-muted">{c.direction}</span>
                    </td>
                    <td className="num py-1.5 text-[11.5px]">
                      {new Date(c.open_time).toLocaleDateString("he-IL")}
                    </td>
                    <td className="num py-1.5 text-[11.5px]">
                      {c.close_time ? (
                        new Date(c.close_time).toLocaleDateString("he-IL")
                      ) : (
                        <span className="rounded-sm bg-subtle px-1.5 py-px text-[9.5px] text-accent">פתוח</span>
                      )}
                    </td>
                    <td className="num py-1.5 text-end">{c.holding_days}</td>
                    <td className="py-1.5 text-end"><Num value={c.max_quantity} kind="qty" /></td>
                    <td className="py-1.5 text-end"><Num value={c.realized_pnl} signed /></td>
                    <td className="py-1.5 text-end"><Num value={c.fees_total} /></td>
                    <td className="py-1.5 text-[11.5px] text-muted">{c.journal?.strategy ?? "—"}</td>
                    <td className="num py-1.5">{c.journal?.rating ? "★".repeat(c.journal.rating) : "—"}</td>
                    <td className="py-1.5">
                      <button
                        type="button"
                        onClick={() => setEditing(c)}
                        className="rounded-sm border border-line px-2 py-0.5 text-[10.5px] text-muted hover:bg-subtle hover:text-fg"
                      >
                        {c.journal ? "ערוך רשומה" : "הוסף רשומה"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {editing && (
        <JournalEntryForm
          cycle={editing}
          onClose={() => {
            setEditing(null);
            queryClient.invalidateQueries({ queryKey: ["journal"] });
          }}
        />
      )}

      <Panel
        title="ניתוח לפי קטגוריה"
        actions={
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="rounded-sm border border-line bg-bg px-2 py-0.5 text-[11.5px] outline-none"
          >
            {DIMENSIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        }
      >
        {analytics.data?.buckets.length ? (
          <>
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-[10.5px] text-faint">
                  <th className="pb-1.5 text-start font-normal">קטגוריה</th>
                  <th className="pb-1.5 text-end font-normal">עסקאות</th>
                  <th className="pb-1.5 text-end font-normal">Win Rate</th>
                  <th className="pb-1.5 text-end font-normal">P&L כולל</th>
                  <th className="pb-1.5 text-end font-normal">P&L ממוצע</th>
                  <th className="pb-1.5 text-end font-normal">עמלות</th>
                </tr>
              </thead>
              <tbody>
                {analytics.data.buckets.map((b) => (
                  <tr key={b.key} className="border-t border-line">
                    <td className="py-1.5">
                      {b.key}
                      {b.small_sample && (
                        <span className="ms-2 rounded-sm bg-subtle px-1 text-[9px] text-warn" title="פחות מ-10 עסקאות — מדגם קטן, אל תסיק מסקנות חזקות">
                          מדגם קטן
                        </span>
                      )}
                    </td>
                    <td className="num py-1.5 text-end">{b.count}</td>
                    <td className="py-1.5 text-end"><Num value={b.win_rate} asPct /></td>
                    <td className="py-1.5 text-end"><Num value={b.total_pnl} signed /></td>
                    <td className="py-1.5 text-end"><Num value={b.avg_pnl} signed /></td>
                    <td className="py-1.5 text-end"><Num value={b.total_fees} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[10.5px] text-faint">{analytics.data.note}</p>
          </>
        ) : (
          <p className="py-6 text-center text-[12.5px] text-muted">
            הניתוח יופיע כשיהיו מחזורי עסקה סגורים.
          </p>
        )}
      </Panel>
    </div>
  );
}
