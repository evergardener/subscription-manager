import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { SessionProvider } from "./app/session";
import { OfflineProvider } from "./offline/OfflineProvider";

function renderApp(path = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <OfflineProvider><SessionProvider><App /></SessionProvider></OfflineProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}

function mockApi(options: { bootstrapNeeded: boolean }) {
  let bootstrapped = false;
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = init?.method ?? "GET";
    if (url.includes("/api/v1/auth/session")) return Promise.resolve(new Response(null, { status: 401 }));
    if (url.includes("/api/v1/auth/bootstrap") && method === "GET") return Promise.resolve(json({ required: options.bootstrapNeeded && !bootstrapped }));
    if (url.includes("/api/v1/auth/bootstrap") && method === "POST") { bootstrapped = true; return Promise.resolve(json({ id: "user-1", username: "admin" }, 201)); }
    if (url.includes("/api/v1/auth/login")) return Promise.resolve(json({ username: "admin", csrf_token: "csrf" }));
    if (url.includes("/api/v1/subscriptions")) return Promise.resolve(json({ items: [], page: 1, page_size: 100, total: 0 }));
    if (url.includes("/api/v1/events/upcoming")) return Promise.resolve(json([]));
    if (url.includes("/api/v1/exchange-rates/latest")) return Promise.resolve(json({ base: "CNY", date: "2026-07-17", source: "European Central Bank", source_url: "https://www.ecb.europa.eu/", rates: { CNY: "1", USD: "6.75" } }));
    return Promise.resolve(new Response(null, { status: 404 }));
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

test("redirects an unauthenticated visitor to the login page", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 401 }));
  renderApp();
  expect(screen.getByText("正在恢复会话…")).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "欢迎回来" })).toBeInTheDocument();
});

test("logs in and opens the protected application shell", async () => {
  mockApi({ bootstrapNeeded: false });
  renderApp("/login");
  await screen.findByRole("heading", { name: "欢迎回来" });
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "correct horse battery staple" } });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));
  expect(await screen.findByRole("heading", { name: "今天，一切按计划。" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
});

test("creates the first administrator and signs in from the setup form", async () => {
  mockApi({ bootstrapNeeded: true });
  renderApp("/login");
  expect(await screen.findByRole("heading", { name: "首次设置" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "correct horse battery staple" } });
  fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "correct horse battery staple" } });
  fireEvent.click(screen.getByRole("button", { name: "创建并登录" }));
  expect(await screen.findByRole("heading", { name: "今天，一切按计划。" })).toBeInTheDocument();
});
