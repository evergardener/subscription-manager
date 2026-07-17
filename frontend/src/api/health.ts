export interface HealthResponse {
  status: "ok" | "not_ready";
}

export async function fetchLiveHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health/live", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}
