"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchHealth } from "@/lib/api";

/*
  The always-visible connection strip: LIVE · READ ONLY · CONNECTED.
  Until the gateway integration lands (phase 3), it truthfully reports
  the backend + database state and marks IBKR as not connected.
*/
export function ConnectionStatus() {
  const { data, isError, dataUpdatedAt } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });

  const gateway = data?.components?.ibkr_gateway?.status === "ok";
  const backendUp = !isError && data !== undefined;

  return (
    <div className="flex items-center gap-3" dir="ltr">
      <span className="sym flex items-center gap-1.5 text-[11px] font-medium tracking-wide">
        <Dot ok={gateway} />
        {gateway ? "LIVE · READ ONLY · CONNECTED" : backendUp ? "IBKR · NOT CONNECTED" : "BACKEND · DOWN"}
      </span>
      {dataUpdatedAt > 0 && (
        <span className="num text-[10.5px] text-faint">
          {new Date(dataUpdatedAt).toLocaleTimeString("en-GB")}
        </span>
      )}
    </div>
  );
}

function Dot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden
      className={`inline-block size-1.5 rounded-full ${ok ? "bg-gain" : "bg-loss"}`}
    />
  );
}
