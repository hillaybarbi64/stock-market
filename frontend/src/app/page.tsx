"use client";

import { useQuery } from "@tanstack/react-query";
import { Panel } from "@/components/ui/panel";
import { fetchHealth } from "@/lib/api";

export default function OverviewPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight">סקירה כללית</h1>
        <p className="mt-0.5 text-[12.5px] text-muted">
          תמונת המצב החיה של החשבון תופיע כאן לאחר חיבור ה־Gateway (שלב 4).
        </p>
      </div>

      <Panel title="מצב המערכת">
        {isLoading ? (
          <div className="h-16 animate-pulse rounded-sm bg-subtle" />
        ) : isError ? (
          <p className="text-[13px] text-loss">
            ה־Backend אינו זמין. הפעל אותו עם <span className="sym">./scripts/start.sh</span>
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-4">
            <StatusItem label="Backend" ok />
            <StatusItem label="Database" ok={data?.components.database?.status === "ok"} />
            <StatusItem
              label="IBKR Gateway"
              ok={data?.components.ibkr_gateway?.status === "ok"}
              note={
                data?.components.ibkr_gateway?.status !== "ok" ? "יחובר בשלב 3" : undefined
              }
            />
            <div>
              <dt className="text-[11.5px] text-faint">גרסה</dt>
              <dd className="num mt-0.5">{data?.version}</dd>
            </div>
          </dl>
        )}
      </Panel>
    </div>
  );
}

function StatusItem({ label, ok, note }: { label: string; ok?: boolean; note?: string }) {
  return (
    <div>
      <dt className="text-[11.5px] text-faint">
        <span className="sym">{label}</span>
      </dt>
      <dd className="mt-0.5 flex items-center gap-1.5">
        <span className={`size-1.5 rounded-full ${ok ? "bg-gain" : "bg-loss"}`} aria-hidden />
        <span>{ok ? "תקין" : note ?? "לא זמין"}</span>
      </dd>
    </div>
  );
}
