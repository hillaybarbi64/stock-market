"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Panel } from "@/components/ui/panel";
import { apiGet, apiPost } from "@/lib/api";

interface InsightRow {
  id: number;
  kind: string;
  severity: "INFO" | "WARN" | "ALERT";
  confidence: "LOW" | "MED" | "HIGH";
  title: string;
  body: string;
  evidence: Record<string, unknown>;
  assumptions: string | null;
  links: { page?: string } | null;
  created_at: string;
}

const SEVERITY_LABEL = { INFO: "מידע", WARN: "לתשומת לב", ALERT: "חשוב" } as const;
const CONFIDENCE_LABEL = { LOW: "ביטחון נמוך", MED: "ביטחון בינוני", HIGH: "ביטחון גבוה" } as const;

export default function InsightsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["insights"],
    queryFn: () => apiGet<{ insights: InsightRow[] }>("/risk/insights"),
  });
  const refresh = useMutation({
    mutationFn: () => apiPost("/risk/insights/refresh"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["insights"] }),
  });
  const dismiss = useMutation({
    mutationFn: (id: number) => apiPost(`/risk/insights/${id}/dismiss`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["insights"] }),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">תובנות</h1>
        <button
          type="button"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="rounded-sm border border-line px-3 py-1 text-[12px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-40"
        >
          {refresh.isPending ? "בודק…" : "רענן תובנות"}
        </button>
      </div>

      <p className="text-[11.5px] leading-relaxed text-muted">
        כל תובנה מבוססת על נתונים ספציפיים מהחשבון שלך, עם רמת חומרה, רמת ביטחון וההנחות
        שמאחוריה. אלה נקודות לבדיקה — לא הוראות פעולה, והמערכת לעולם לא תבצע עסקה.
      </p>

      {isLoading ? (
        <div className="h-40 animate-pulse rounded-md bg-subtle" />
      ) : !data?.insights.length ? (
        <Panel>
          <div className="py-10 text-center">
            <p className="text-[13.5px] font-medium">אין תובנות פתוחות</p>
            <p className="mt-1 text-[12.5px] text-muted">
              לחץ &quot;רענן תובנות&quot; כדי להריץ את הכללים על המצב הנוכחי. תובנות נוצרות
              רק כשיש להן בסיס בנתונים.
            </p>
          </div>
        </Panel>
      ) : (
        <div className="space-y-3">
          {data.insights.map((i) => (
            <div key={i.id} className="rounded-md border border-line bg-panel p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-sm px-1.5 py-px text-[9.5px] font-medium ${
                      i.severity === "ALERT"
                        ? "bg-loss/15 text-loss"
                        : i.severity === "WARN"
                          ? "bg-warn/15 text-warn"
                          : "bg-subtle text-muted"
                    }`}
                  >
                    {SEVERITY_LABEL[i.severity]}
                  </span>
                  <span className="text-[9.5px] text-faint">{CONFIDENCE_LABEL[i.confidence]}</span>
                  <span className="num text-[9.5px] text-faint">
                    {new Date(i.created_at).toLocaleDateString("he-IL")}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => dismiss.mutate(i.id)}
                  className="text-[10.5px] text-faint hover:text-fg"
                >
                  הסתר
                </button>
              </div>
              <h2 className="mt-2 text-[13.5px] font-semibold">{i.title}</h2>
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{i.body}</p>
              {i.assumptions && (
                <p className="mt-2 text-[10.5px] text-faint">הנחות: {i.assumptions}</p>
              )}
              <div className="mt-2 flex items-center gap-3">
                {i.links?.page && (
                  <Link href={i.links.page} className="text-[11px] text-accent hover:underline">
                    ← לנתונים הרלוונטיים
                  </Link>
                )}
                <details className="text-[10.5px] text-faint">
                  <summary className="cursor-pointer hover:text-muted">הנתונים שבבסיס התובנה</summary>
                  <pre className="num mt-1 max-w-full overflow-x-auto rounded-sm bg-subtle p-2 text-[10px]" dir="ltr">
                    {JSON.stringify(i.evidence, null, 1)}
                  </pre>
                </details>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
