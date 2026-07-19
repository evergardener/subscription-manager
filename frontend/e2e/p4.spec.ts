import { expect, test, type Page } from "@playwright/test";

const username = "p4-admin";
const password = "p4-validation-password";

async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "今天，一切按计划。" })).toBeVisible();
}

test.beforeAll(async ({ request }) => {
  const response = await request.post("/api/v1/auth/bootstrap", {
    data: { username, password },
  });
  if (response.status() === 201) return;
  expect(response.status()).toBe(409);
  const loginResponse = await request.post("/api/v1/auth/login", {
    data: { username, password },
  });
  expect(loginResponse.ok(), "A pre-existing administrator must match the isolated E2E credentials").toBeTruthy();
});

test("complete authenticated P4 workflow", async ({ page, context }, testInfo) => {
  const subscriptionName = `P4 Validation ${testInfo.project.name}`;
  const tokenName = `P4 token ${testInfo.project.name}`;
  await login(page);
  const shellResponse = await context.request.get("/");
  expect(shellResponse.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(shellResponse.headers()["x-content-type-options"]).toBe("nosniff");
  const healthResponse = await context.request.get("/api/v1/health/ready");
  expect(healthResponse.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(healthResponse.headers()["x-content-type-options"]).toBe("nosniff");
  await page.getByRole("link", { name: "＋ 新建订阅" }).click();
  await page.getByLabel("名称").fill(subscriptionName);
  await page.getByLabel("供应商").fill("Hermes Labs");
  await page.getByLabel("金额").fill("29.99");
  const nextMonth = new Date();
  nextMonth.setMonth(nextMonth.getMonth() + 1, 10);
  await expect(page.getByLabel("币种")).toHaveValue("CNY");
  await page.getByLabel("到期后继续自动续费").uncheck();
  await page.getByLabel("下次续费").fill(nextMonth.toISOString().slice(0, 10));
  await page.getByRole("button", { name: "创建订阅" }).click();
  await expect(page.getByRole("heading", { name: subscriptionName })).toBeVisible();
  await page.getByRole("heading", { name: subscriptionName }).click();
  await expect(page.getByRole("heading", { name: "计费计划" })).toBeVisible();
  await expect(page.getByText("已关闭", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← 所有订阅" }).click();
  const nonRenewingCard = page.locator(".subscription-card").filter({ hasText: subscriptionName });
  await expect(nonRenewingCard.getByText("已关闭自动续费", { exact: true })).toBeVisible();
  await nonRenewingCard.click();

  const datesPanel = page.locator("section.panel").filter({ has: page.getByRole("heading", { name: "关键日期" }) });
  await datesPanel.getByRole("button", { name: "编辑", exact: true }).click();
  const datesDialog = page.getByRole("dialog", { name: "编辑关键日期" });
  await datesDialog.getByLabel("服务到期").fill(nextMonth.toISOString().slice(0, 10));
  await datesDialog.getByRole("button", { name: "保存日期" }).click();
  await expect(datesPanel).toContainText(`服务到期${nextMonth.toISOString().slice(0, 10)}`);

  await page.getByRole("button", { name: "编辑计划" }).click();
  await page.getByLabel("到期后继续自动续费").check();
  await page.getByRole("button", { name: "保存更改" }).click();
  await expect(page.getByText("已开启", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "＋ 记录付款" }).click();
  const paymentDialog = page.getByRole("dialog", { name: "记录实际付款" });
  await expect(paymentDialog.getByLabel("推进到下一账期")).toBeChecked();
  await paymentDialog.getByRole("button", { name: "记录付款" }).click();
  await expect(page.getByText("manual", { exact: true })).toBeVisible();
  const updatedDetail = await context.request.get(`/api/v1/subscriptions/${new URL(page.url()).pathname.split("/").pop()}`);
  expect(updatedDetail.ok()).toBeTruthy();
  const subscriptionId = new URL(page.url()).pathname.split("/").pop() as string;
  const detailBody = (await updatedDetail.json()) as { billing_plan: { next_billing_date: string | null } };
  expect(detailBody.billing_plan.next_billing_date).not.toBe(nextMonth.toISOString().slice(0, 10));

  const remindersPanel = page.locator("section.panel").filter({ has: page.getByRole("heading", { name: "提醒", exact: true }) });
  await remindersPanel.getByRole("button", { name: "编辑", exact: true }).click();
  const rules = page.getByRole("dialog", { name: "续费提醒" });
  await rules.getByLabel("第一条（提前天数）").fill("5");
  await rules.getByLabel("第二条（提前天数）").fill("1");
  await rules.getByRole("button", { name: "保存提醒" }).click();
  await expect(page.getByText("提前 5 天 · billing")).toBeVisible();
  await expect(page.getByText("提前 1 天 · billing")).toBeVisible();

  await page.getByRole("button", { name: "计划取消", exact: true }).click();
  const cancelDialog = page.getByRole("dialog", { name: "计划取消订阅" });
  await cancelDialog.getByLabel("服务到期").fill(nextMonth.toISOString().slice(0, 10));
  await cancelDialog.getByLabel("原因").fill("E2E cancellation validation");
  await cancelDialog.getByRole("button", { name: "确认计划取消" }).click();
  await expect(page.getByText("pending_cancel", { exact: true })).toBeVisible();
  await expect(page.getByText("已关闭", { exact: true })).toBeVisible();
  const cancelledEventsResponse = await context.request.get("/api/v1/events/upcoming?days=366");
  expect(cancelledEventsResponse.ok()).toBeTruthy();
  const cancelledEvents = (await cancelledEventsResponse.json()) as Array<{ subscription_id: string; event_type: string; event_date: string; status: string }>;
  expect(cancelledEvents.filter((event) => event.subscription_id === subscriptionId && event.event_type === "billing" && event.event_date > nextMonth.toISOString().slice(0, 10))).toHaveLength(0);

  await page.getByRole("button", { name: "撤销取消", exact: true }).click();
  const resumeDialog = page.getByRole("dialog", { name: "撤销取消计划" });
  await resumeDialog.getByLabel("原因").fill("E2E cancellation withdrawn");
  await resumeDialog.getByRole("button", { name: "确认撤销" }).click();
  await expect(page.getByText("active", { exact: true })).toBeVisible();
  await expect(page.getByText("已开启", { exact: true })).toBeVisible();
  const restoredEventsResponse = await context.request.get("/api/v1/events/upcoming?days=366");
  expect(restoredEventsResponse.ok()).toBeTruthy();
  const restoredEvents = (await restoredEventsResponse.json()) as Array<{ subscription_id: string; event_type: string; event_date: string; status: string }>;
  expect(restoredEvents.some((event) => event.subscription_id === subscriptionId && event.event_type === "billing" && event.event_date > nextMonth.toISOString().slice(0, 10) && event.status === "planned")).toBeTruthy();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "归档", exact: true }).click();
  await page.getByLabel("显示已归档").check();
  await page.getByRole("heading", { name: subscriptionName }).click();
  await page.getByRole("button", { name: "恢复", exact: true }).click();
  await expect(page.getByText("active", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "＋ 创建" }).click();
  const tokenDialog = page.getByRole("dialog", { name: "创建 API Token" });
  await tokenDialog.getByLabel("名称").fill(tokenName);
  await tokenDialog.getByRole("button", { name: "创建 Token" }).click();
  const revealDialog = page.getByRole("dialog", { name: "保存 API Token" });
  await expect(revealDialog).toContainText("hsm_");
  const rawToken = (await revealDialog.locator("code").textContent()) as string;
  const bearerHeaders = { Authorization: `Bearer ${rawToken}` };
  expect((await context.request.get("/api/v1/audit-logs", { headers: bearerHeaders })).status()).toBe(403);
  expect((await context.request.get("/api/v1/api-tokens", { headers: bearerHeaders })).status()).toBe(403);
  await page.getByRole("button", { name: "我已安全保存" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  const tokenRow = page.locator(".token-list article").filter({ hasText: tokenName });
  await tokenRow.getByRole("button", { name: "撤销", exact: true }).click();
  await expect(tokenRow.getByText("已撤销", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "订阅", exact: true }).click();
  await context.setOffline(true);
  await expect(page.getByText("离线只读", { exact: true })).toBeVisible();
  await expect(page.getByText(/数据可能已过期|写操作已禁用/)).toBeVisible();
  await expect(page.getByRole("button", { name: "＋ 新建订阅" })).toBeDisabled();
  await context.setOffline(false);

  const dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width);

  if (testInfo.project.name === "mobile-360") {
    const changedPassword = "p4-validation-password-changed";
    await page.getByRole("link", { name: "设置", exact: true }).click();
    await page.getByRole("button", { name: "修改密码", exact: true }).click();
    const passwordDialog = page.getByRole("dialog", { name: "修改密码" });
    await passwordDialog.getByLabel("当前密码").fill(password);
    await passwordDialog.getByLabel("新密码", { exact: true }).fill(changedPassword);
    await passwordDialog.getByLabel("再次输入新密码").fill(changedPassword);
    await passwordDialog.getByRole("button", { name: "修改并退出全部设备" }).click();
    await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码").fill(changedPassword);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await expect(page.getByRole("heading", { name: "今天，一切按计划。" })).toBeVisible();
    await page.getByRole("link", { name: "设置", exact: true }).click();
    await page.getByRole("button", { name: "修改密码", exact: true }).click();
    const restorePasswordDialog = page.getByRole("dialog", { name: "修改密码" });
    await restorePasswordDialog.getByLabel("当前密码").fill(changedPassword);
    await restorePasswordDialog.getByLabel("新密码", { exact: true }).fill(password);
    await restorePasswordDialog.getByLabel("再次输入新密码").fill(password);
    await restorePasswordDialog.getByRole("button", { name: "修改并退出全部设备" }).click();
    await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await expect(page.getByRole("heading", { name: "今天，一切按计划。" })).toBeVisible();
  }

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  const cachedResponses = await page.evaluate(
    () =>
      new Promise<number>((resolve, reject) => {
        const request = indexedDB.open("hermes-business-cache");
        request.onerror = () => reject(new Error("Could not open the offline cache", { cause: request.error }));
        request.onsuccess = () => {
          const database = request.result;
          if (!database.objectStoreNames.contains("responses")) {
            resolve(0);
            return;
          }
          const count = database.transaction("responses", "readonly").objectStore("responses").count();
          count.onerror = () => reject(new Error("Could not count cached responses", { cause: count.error }));
          count.onsuccess = () => resolve(count.result);
        };
      }),
  );
  expect(cachedResponses).toBe(0);
});
