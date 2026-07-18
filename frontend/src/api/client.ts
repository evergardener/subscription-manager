export type ApiErrorBody = {
  code?: string;
  message?: string;
  details?: unknown;
  request_id?: string | null;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: ApiErrorBody,
  ) {
    super(body.message ?? `请求失败（${status}）`);
  }
}

let csrfToken: string | null = null;

export function setCsrfToken(value: string | null) {
  csrfToken = value;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!new Set(["GET", "HEAD", "OPTIONS"]).has(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    let body: ApiErrorBody = { message: `请求失败（${response.status}）` };
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Preserve the generic message for non-JSON proxy errors.
    }
    throw new ApiError(response.status, body);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
