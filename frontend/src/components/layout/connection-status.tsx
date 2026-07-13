"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchConnection, postReconnect, type GatewayState } from "@/lib/api";

/*
  The always-visible connection strip.
  Connected:      ● LIVE · READ ONLY · CONNECTED        (+ delayed marker if relevant)
  Disconnected:   ● GATEWAY DOWN · retry in Ns          (+ manual reconnect button)
  Data is never presented as fresh when it isn't — the strip shows the last
  update time whenever the connection is anything but CONNECTED.
*/

const STATE_LABEL: Record<GatewayState, string> = {
  connected: "LIVE · READ ONLY · CONNECTED",
  connecting: "CONNECTING…",
  disconnected: "DISCONNECTED",
  gateway_down: "GATEWAY DOWN",
  auth_required: "LOGIN REQUIRED",
};

export function ConnectionStatus() {
  const queryClient = useQueryClient();
  const { data, isError } = useQuery({
    queryKey: ["connection"],
    queryFn: fetchConnection,
    refetchInterval: 5_000,
  });

  const reconnect = useMutation({
    mutationFn: postReconnect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connection"] }),
  });

  if (isError || !data) {
    return (
      <span className="sym flex items-center gap-1.5 text-[11px] font-medium tracking-wide" dir="ltr">
        <Dot tone="loss" /> BACKEND · DOWN
      </span>
    );
  }

  const connected = data.state === "connected";
  const tone = connected ? "gain" : data.state === "connecting" ? "warn" : "loss";

  return (
    <div className="flex items-center gap-3" dir="ltr">
      <span className="sym flex items-center gap-1.5 text-[11px] font-medium tracking-wide">
        <Dot tone={tone} />
        {STATE_LABEL[data.state]}
        {connected && data.market_data_type === "delayed" && (
          <span className="rounded-sm bg-subtle px-1 py-px text-[9.5px] text-warn">DELAYED</span>
        )}
      </span>

      {!connected && data.last_update && (
        <span className="num text-[10.5px] text-faint" title="זמן העדכון האחרון שהתקבל">
          last: {new Date(data.last_update).toLocaleTimeString("en-GB")}
        </span>
      )}
      {!connected && data.next_retry_in_s != null && (
        <span className="num text-[10.5px] text-faint">retry {data.next_retry_in_s}s</span>
      )}
      {!connected && (
        <button
          type="button"
          onClick={() => reconnect.mutate()}
          disabled={reconnect.isPending}
          className="rounded-sm border border-line px-2 py-0.5 text-[10.5px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-50"
        >
          Reconnect
        </button>
      )}
    </div>
  );
}

function Dot({ tone }: { tone: "gain" | "loss" | "warn" }) {
  const cls = tone === "gain" ? "bg-gain" : tone === "warn" ? "bg-warn" : "bg-loss";
  return <span aria-hidden className={`inline-block size-1.5 rounded-full ${cls}`} />;
}
