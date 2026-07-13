"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import type { ConnectionInfo } from "@/lib/api";

const WS_URL =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws") + "/api/ws";

interface WsMessage {
  type: string;
  data: Record<string, unknown>;
  ts: string;
}

/*
  Single app-wide WebSocket. Incoming deltas are merged into the TanStack
  Query cache so components re-render only for the data they use — no page
  refreshes, no flicker. If the socket drops we retry with capped backoff;
  REST polling continues to work regardless.
*/
export function useLiveUpdates() {
  const queryClient = useQueryClient();

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let attempt = 0;

    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        attempt = 0;
      };
      ws.onmessage = (event) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(event.data as string) as WsMessage;
        } catch {
          return;
        }
        handleMessage(msg);
      };
      ws.onclose = () => {
        if (closed) return;
        attempt += 1;
        const delay = Math.min(30_000, 1_000 * 2 ** attempt);
        setTimeout(connect, delay);
      };
    };

    const handleMessage = (msg: WsMessage) => {
      if (msg.type === "connection") {
        queryClient.setQueryData(["connection"], msg.data as unknown as ConnectionInfo);
      } else if (msg.type === "account_summary") {
        queryClient.setQueryData(["account", "summary"], {
          source: "ibkr_gateway",
          stale: false,
          as_of: (msg.data.ts as string) ?? msg.ts,
          data: msg.data,
        });
      } else if (msg.type === "cash_balances") {
        queryClient.setQueryData(["account", "balances"], {
          source: "ibkr_gateway",
          stale: false,
          balances: msg.data.balances,
        });
      } else if (msg.type.startsWith("position:")) {
        // Cheap and correct: refetch the positions list (single user, small N).
        queryClient.invalidateQueries({ queryKey: ["positions"] });
      } else if (msg.type === "execution" || msg.type.startsWith("order:")) {
        queryClient.invalidateQueries({ queryKey: ["trades"] });
        queryClient.invalidateQueries({ queryKey: ["orders"] });
      }
    };

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [queryClient]);
}
