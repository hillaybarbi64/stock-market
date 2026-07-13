const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}/api${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

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

export function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/system/health");
}
