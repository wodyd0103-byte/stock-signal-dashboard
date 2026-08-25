import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 신호 이력 패널. 값은 digest CLI 가 남긴 것을 읽어 보여줄 뿐이라, 여기서 볼 것은
 * 배선이다 — 리서치 탭에 붙어 있는지, 펼치기 전에는 요청하지 않는지, 펼치면
 * 기록이 화면에 오르는지.
 */
test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("combobox").waitFor();
  await page.getByRole("tab", { name: "리서치" }).click();
});

test("리서치 탭에 신호 이력 패널이 있고, 펼치기 전에는 조회하지 않는다", async ({ page }) => {
  const calls: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("signal-changes")) calls.push(req.url());
  });

  await expect(page.getByRole("heading", { name: "이 종목, 원래 자주 뒤집히나?" })).toBeVisible();
  expect(calls).toHaveLength(0);
});

test("펼치면 전환 횟수와 최근 전환이 뜬다", async ({ page }) => {
  await page.getByRole("button", { name: /자주 뒤집히나/ }).click();

  const panel = page.locator("section", { hasText: "이 종목, 원래 자주 뒤집히나?" });
  await expect(panel.getByText("자주 뒤집힌 종목", { exact: false })).toBeVisible();
  await expect(panel.getByText("3회")).toBeVisible();
  await expect(panel.getByText("BUY → HOLD").first()).toBeVisible();
});

test("기간을 90일로 바꾸면 그 기간으로 다시 읽는다", async ({ page }) => {
  const windows: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    if (url.includes("signal-changes")) windows.push(new URL(url).searchParams.get("days") ?? "");
  });

  await page.getByRole("button", { name: /자주 뒤집히나/ }).click();
  await expect(page.getByText("자주 뒤집힌 종목", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "90일" }).click();

  await expect.poll(() => windows).toContain("90");
});
