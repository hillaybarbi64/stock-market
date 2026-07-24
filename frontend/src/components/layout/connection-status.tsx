"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchConnection, postReconnect, type GatewayState } from "@/lib/api";

/*
  The always-visible connection strip.
  Connected:      ● LIVE · APP READ-ONLY                (+ delayed marker if relevant)
  Disconnected:   ● GATEWAY DOWN · retry in Ns          (+ manual reconnect button)
  Data is never presented as fresh when it isn't — the strip shows the last
  update time whenever the connection is anything but CONNECTED.
*/

const STATE_LABEL: Record<GatewayState, string> = {
  connected: "LIVE · APP READ-ONLY",
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
      <span
        className="sym inline-flex items-center gap-2 rounded-lg border border-[color-mix(in_srgb,var(--loss)_34%,transparent)] bg-[color-mix(in_srgb,var(--loss)_12%,transparent)] px-2.5 py-1 text-[10.5px] font-semibold tracking-[0.06em] text-loss"
        dir="ltr"
      >
        <Dot tone="loss" /> BACKEND · DOWN
      </span>
    );
  }

  const connected = data.state === "connected";

  // Connected → the signature green pill.
  if (connected) {
    return (
      <span
        className="sym inline-flex items-center gap-2 rounded-lg border border-[color-mix(in_srgb,var(--accent)_30%,transparent)] bg-accent-soft px-2.5 py-1 text-[10.5px] font-semibold tracking-[0.06em] text-up-bright"
        dir="ltr"
      >
        <Dot tone="gain" />
        {STATE_LABEL.connected}
        {data.market_data_type === "delayed" && (
          <span className="rounded-[4px] border border-[color-mix(in_srgb,var(--warn)_34%,transparent)] px-1 py-px text-[9px] text-warn">
            DELAYED
          </span>
        )}
      </span>
    );
  }

  const tone = data.state === "connecting" ? "warn" : "loss";
  return (
    <div className="flex items-center gap-2.5" dir="ltr">
      <span className="sym flex items-center gap-1.5 text-[10.5px] font-semibold tracking-[0.06em]">
        <Dot tone={tone} />
        {STATE_LABEL[data.state]}
      </span>
      {data.last_update && (
        <span className="num text-[10.5px] text-faint" title="זמן העדכון האחרון שהתקבל">
          last: {new Date(data.last_update).toLocaleTimeString("en-GB")}
        </span>
      )}
      {data.next_retry_in_s != null && (
        <span className="num text-[10.5px] text-faint">retry {data.next_retry_in_s}s</span>
      )}
      <button
        type="button"
        onClick={() => reconnect.mutate()}
        disabled={reconnect.isPending}
        className="press rounded-md border border-line px-2 py-0.5 text-[10.5px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-50"
      >
        Reconnect
      </button>
    </div>
  );
}

function Dot({ tone }: { tone: "gain" | "loss" | "warn" }) {
  // gain (live) → breathing ring; warn (connecting) → blink; loss → steady solid.
  const cls =
    tone === "gain"
      ? "bg-gain live-dot"
      : tone === "warn"
        ? "bg-warn live-connecting"
        : "bg-loss";
  return <span aria-hidden className={`inline-block size-1.5 rounded-full ${cls}`} />;
}
