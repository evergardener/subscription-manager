import { apiRequest } from "./client";

export type Session = { actor_type: string; actor_id: string; csrf_token?: string };
export type LoginResult = { username: string; csrf_token: string };
export type ApiTokenRecord = { id: string; name: string; actor_type: string; actor_id: string; scopes: string[]; expires_at: string | null; revoked_at: string | null };

export function getSession(signal?: AbortSignal) {
  return apiRequest<Session>("/api/v1/auth/session", { signal });
}

export function login(username: string, password: string) {
  return apiRequest<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout() {
  return apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}

export function changePassword(current_password: string, new_password: string) {
  return apiRequest<void>("/api/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
}

export function listApiTokens(signal?: AbortSignal) {
  return apiRequest<ApiTokenRecord[]>("/api/v1/api-tokens", { signal });
}

export function createApiToken(payload: { name: string; actor_id: string; scopes: string[] }) {
  return apiRequest<{ id: string; token: string; scopes: string[] }>("/api/v1/api-tokens", {
    method: "POST",
    body: JSON.stringify({ ...payload, actor_type: "hermes" }),
  });
}

export function revokeApiToken(id: string) {
  return apiRequest<void>(`/api/v1/api-tokens/${id}`, { method: "DELETE" });
}
