import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { SessionProvider } from "./app/session";

function renderApp(path = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <SessionProvider><App /></SessionProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
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
  const request = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ username: "admin", csrf_token: "csrf" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
  renderApp("/login");
  await screen.findByRole("heading", { name: "欢迎回来" });
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "correct horse battery staple" } });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));
  expect(await screen.findByRole("heading", { name: "总览" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
  expect(request).toHaveBeenCalledTimes(2);
});
