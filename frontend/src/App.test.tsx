import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { App } from "./App";


function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

test("shows API ready when the live endpoint succeeds", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  renderApp();

  expect(screen.getByText("正在连接 API")).toBeInTheDocument();
  expect(await screen.findByText("API 已就绪")).toBeInTheDocument();
});

test("shows an unavailable state when the live endpoint fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 503 }));

  renderApp();

  expect(await screen.findByText("API 暂不可用")).toBeInTheDocument();
});
