import { apiRequest } from "./client";

export type Session = { actor_type: string; actor_id: string; csrf_token?: string };
export type LoginResult = { username: string; csrf_token: string };

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
