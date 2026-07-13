"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { CycleRow } from "@/app/journal/page";
import { Sym } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

interface EntryPayload {
  cycle_id: number;
  strategy: string | null;
  setup: string | null;
  catalyst: string | null;
  thesis: string | null;
  entry_reason: string | null;
  exit_reason: string | null;
  invalidation: string | null;
  target_price: string | null;
  stop_price: string | null;
  planned_rr: string | null;
  confidence: number | null;
  emotional_state: string | null;
  followed_plan: boolean | null;
  changed_plan_midway: boolean | null;
  mistake: string | null;
  done_right: string | null;
  key_lesson: string | null;
  next_time: string | null;
  rating: number | null;
  free_notes: string | null;
  template_id: number | null;
}

interface ExistingEntry extends EntryPayload {
  id: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EMOTIONS = ["רגוע", "בטוח", "לחוץ", "חמדני", "פוחד להחמיץ", "מתוסכל", "עייף", "נקמני"];

export function JournalEntryForm({ cycle, onClose }: { cycle: CycleRow; onClose: () => void }) {
  const existing = useQuery({
    queryKey: ["journal", "entry", cycle.id],
    queryFn: () => apiGet<{ entries: ExistingEntry[] }>(`/journal/entries?cycle_id=${cycle.id}`),
  });

  if (existing.isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="widget px-6 py-4 text-[12.5px] text-muted">
          טוען רשומה…
        </div>
      </div>
    );
  }
  return <FormInner cycle={cycle} entry={existing.data?.entries[0]} onClose={onClose} />;
}

function FormInner({
  cycle,
  entry,
  onClose,
}: {
  cycle: CycleRow;
  entry: ExistingEntry | undefined;
  onClose: () => void;
}) {
  const templates = useQuery({
    queryKey: ["journal", "templates"],
    queryFn: () => apiGet<{ templates: { id: number; name: string }[] }>("/journal/templates"),
  });

  const [form, setForm] = useState<Partial<EntryPayload>>(entry ?? {});

  const save = useMutation({
    mutationFn: async () => {
      const payload = { ...form, cycle_id: cycle.id };
      const url = entry
        ? `${API_URL}/api/journal/entries/${entry.id}`
        : `${API_URL}/api/journal/entries`;
      const res = await fetch(url, {
        method: entry ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`save failed: ${res.status}`);
      return res.json();
    },
    onSuccess: onClose,
  });

  const set = (key: keyof EntryPayload, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value === "" ? null : value }));

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-6 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="max-h-full w-full max-w-2xl overflow-y-auto rounded-md border border-line bg-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 flex items-center justify-between border-b border-line bg-panel px-4 py-3">
          <h2 className="text-[14px] font-semibold">
            רשומת יומן · <Sym>{cycle.symbol}</Sym>{" "}
            <span className="text-[11px] font-normal text-faint">
              {cycle.direction} · {new Date(cycle.open_time).toLocaleDateString("he-IL")}
            </span>
          </h2>
          <button type="button" onClick={onClose} className="text-[12px] text-muted hover:text-fg">
            סגור
          </button>
        </header>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3 p-4">
          <L label="תבנית">
            <select
              value={form.template_id ?? ""}
              onChange={(e) => set("template_id", e.target.value ? Number(e.target.value) : null)}
              className={INPUT}
            >
              <option value="">ללא</option>
              {templates.data?.templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </L>
          <L label="אסטרטגיה">
            <input value={form.strategy ?? ""} onChange={(e) => set("strategy", e.target.value)} className={INPUT} placeholder="Swing / Breakout / השקעה" />
          </L>
          <L label="Setup">
            <input value={form.setup ?? ""} onChange={(e) => set("setup", e.target.value)} className={INPUT} />
          </L>
          <L label="Catalyst">
            <input value={form.catalyst ?? ""} onChange={(e) => set("catalyst", e.target.value)} className={INPUT} />
          </L>
          <L label="תזה" full>
            <textarea value={form.thesis ?? ""} onChange={(e) => set("thesis", e.target.value)} className={AREA} rows={2} />
          </L>
          <L label="סיבת כניסה" full>
            <textarea value={form.entry_reason ?? ""} onChange={(e) => set("entry_reason", e.target.value)} className={AREA} rows={2} />
          </L>
          <L label="תנאי ביטול התזה" full>
            <textarea value={form.invalidation ?? ""} onChange={(e) => set("invalidation", e.target.value)} className={AREA} rows={1} />
          </L>
          <L label="יעד (מחיר)">
            <input dir="ltr" value={form.target_price ?? ""} onChange={(e) => set("target_price", e.target.value)} className={INPUT + " num"} />
          </L>
          <L label="Stop (מחיר)">
            <input dir="ltr" value={form.stop_price ?? ""} onChange={(e) => set("stop_price", e.target.value)} className={INPUT + " num"} />
          </L>
          <L label="יחס סיכוי/סיכון מתוכנן">
            <input dir="ltr" value={form.planned_rr ?? ""} onChange={(e) => set("planned_rr", e.target.value)} className={INPUT + " num"} placeholder="2.5" />
          </L>
          <L label="רמת ביטחון (1–5)">
            <Rating value={form.confidence ?? null} onChange={(v) => set("confidence", v)} />
          </L>
          <L label="מצב רגשי">
            <select value={form.emotional_state ?? ""} onChange={(e) => set("emotional_state", e.target.value)} className={INPUT}>
              <option value="">—</option>
              {EMOTIONS.map((em) => (
                <option key={em} value={em}>{em}</option>
              ))}
            </select>
          </L>
          <L label="משמעת">
            <div className="flex gap-3 pt-1 text-[12px]">
              <Check label="פעלתי לפי התוכנית" checked={form.followed_plan ?? false} onChange={(v) => set("followed_plan", v)} />
              <Check label="שיניתי תוכנית באמצע" checked={form.changed_plan_midway ?? false} onChange={(v) => set("changed_plan_midway", v)} />
            </div>
          </L>
          <L label="סיבת יציאה" full>
            <textarea value={form.exit_reason ?? ""} onChange={(e) => set("exit_reason", e.target.value)} className={AREA} rows={1} />
          </L>
          <L label="טעות שביצעתי">
            <textarea value={form.mistake ?? ""} onChange={(e) => set("mistake", e.target.value)} className={AREA} rows={2} />
          </L>
          <L label="מה עשיתי נכון">
            <textarea value={form.done_right ?? ""} onChange={(e) => set("done_right", e.target.value)} className={AREA} rows={2} />
          </L>
          <L label="לקח מרכזי" full>
            <textarea value={form.key_lesson ?? ""} onChange={(e) => set("key_lesson", e.target.value)} className={AREA} rows={1} />
          </L>
          <L label="מה אעשה אחרת בפעם הבאה" full>
            <textarea value={form.next_time ?? ""} onChange={(e) => set("next_time", e.target.value)} className={AREA} rows={1} />
          </L>
          <L label="דירוג העסקה (1–5)">
            <Rating value={form.rating ?? null} onChange={(v) => set("rating", v)} />
          </L>
          <L label="הערות חופשיות" full>
            <textarea value={form.free_notes ?? ""} onChange={(e) => set("free_notes", e.target.value)} className={AREA} rows={3} />
          </L>
        </div>

        <footer className="sticky bottom-0 flex items-center justify-between border-t border-line bg-panel px-4 py-3">
          <span className="text-[10.5px] text-faint">
            הרשומה נשמרת מקומית בלבד. דירוג העסקה נפרד מהתוצאה הכספית — עסקה טובה יכולה להפסיד.
          </span>
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="rounded-sm bg-accent px-4 py-1.5 text-[12.5px] font-medium text-accent-fg hover:opacity-90 disabled:opacity-40"
          >
            {save.isPending ? "שומר…" : entry ? "עדכן רשומה" : "שמור רשומה"}
          </button>
        </footer>
      </div>
    </div>
  );
}

const INPUT =
  "w-full rounded-sm border border-line bg-bg px-2 py-1 text-[12.5px] outline-none focus:border-line-strong";
const AREA = INPUT + " resize-y";

function L({ label, full, children }: { label: string; full?: boolean; children: React.ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 text-[10.5px] text-faint ${full ? "col-span-2" : ""}`}>
      {label}
      {children}
    </label>
  );
}

function Rating({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  return (
    <div className="flex gap-1 pt-0.5" dir="ltr">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(value === n ? null : n)}
          className={`size-6 rounded-sm border text-[11px] ${
            value != null && n <= value
              ? "border-accent bg-accent text-accent-fg"
              : "border-line text-muted hover:bg-hover"
          }`}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-1.5 text-muted">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="accent-current" />
      {label}
    </label>
  );
}
