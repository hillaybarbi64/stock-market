const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api${path}`, {
    headers: { Accept: "application/json" },
    ...init,
  });
  if (!res.ok) throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiPost = <T>(path: string) => request<T>(path, { method: "POST" });

// ── types ────────────────────────────────────────────────

export interface ComponentHealth {
  status: "ok" | "degraded" | "down";
  detail?: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  components: Record<string, ComponentHealth>;
}

export type GatewayState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "gateway_down"
  | "auth_required";

export interface ConnectionInfo {
  state: GatewayState;
  readonly: boolean;
  account: string | null;
  connected_since: string | null;
  last_update: string | null;
  last_error: string | null;
  reconnect_attempts: number;
  next_retry_in_s: number | null;
  market_data_type: "realtime" | "delayed" | null;
}

export const fetchHealth = () => apiGet<HealthResponse>("/system/health");
export const fetchConnection = () => apiGet<ConnectionInfo>("/system/connection");
export const postReconnect = () => apiPost<{ ok: boolean }>("/system/reconnect");
