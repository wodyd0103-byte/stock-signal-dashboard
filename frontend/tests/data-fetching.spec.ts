import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./mock-api";
import fs from "node:fs";
import path from "node:path";

/**
 * `hooks/useAsyncData`가 약속한 것을 실제로 지키는지 본다. 두 가지다.
 *
 * - 같은 요청은 다시 보내지 않고, 새로고침 버튼은 서버 캐시까지 무시한다.
 * - 늦게 도착한 응답이 현재 화면을 덮어쓰지 않는다.
 *
 * 두 번째가 이 훅을 만든 이유다. 예전 구조는 컴포넌트가 응답을 받는 즉시
 * setState 했기 때문에, 느린 요청이 나중에 도착하면 사용자가 그 사이 고른
 * 값을 조용히 되돌려놨다.
 */

/** 경로별 요청 수. 쿼리스트링은 따로 모아 force_refresh 여부까지 본다. */
function countRequests(page: Page) {
  const urls: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.pathname.includes("/api/")) urls.push(url.pathname + url.search);
  });
  return {
    matching: (pattern: RegExp) => urls.filter((u) => pattern.test(u)),
  };
}

test("한 번 받아온 목록은 탭을 오가도 다시 요청하지 않는다", async ({ page }) => {
  await mockApi(page);
  const requests = countRequests(page);
  await page.goto("/");
  await expect(page.getByText("기술적 지표")).toBeVisible();

  const rail = page.locator("aside");
  await expect(rail.getByRole("button", { name: /매수 신호/ })).toBeVisible();
  expect(requests.matching(/buy-signals/)).toHaveLength(1);

  // 급등 탐색으로 갔다가 돌아온다. 돌아올 때 매수 신호를 다시 부르면 안 된다.
  await rail.getByRole("button", { name: /급등 탐색/ }).click();
  await expect.poll(() => requests.matching(/surge/).length).toBe(1);
  await rail.getByRole("button", { name: /매수 신호/ }).click();
  await page.waitForTimeout(300);

  expect(requests.matching(/buy-signals/)).toHaveLength(1);
  expect(requests.matching(/surge/)).toHaveLength(1);

  // 새로고침은 다시 요청하되, 서버 캐시도 무시하라고 알린다.
  await rail.getByTitle("새로고침").click();
  await expect.poll(() => requests.matching(/buy-signals/).length).toBe(2);
  expect(requests.matching(/buy-signals/)[1]).toContain("force_refresh=true");
});

test("리밸런싱 요청이 실패하면 조용히 넘어가지 않는다", async ({ page }) => {
  // 픽스처가 없는 엔드포인트라 mockApi가 501로 돌려준다. 예전 PortfolioPanel은
  // 이 실패를 빈 catch로 삼켜서, 버튼을 눌러도 아무 일도 없는 것처럼 보였다.
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByText("기술적 지표")).toBeVisible();
  await page.locator("nav").getByRole("button", { name: "포트폴리오", exact: true }).click();

  // 계산 버튼은 리밸런싱과 최적화 두 곳에 있고, DOM 순서상 앞이 리밸런싱이다.
  await expect(page.getByText("리밸런싱 계산기")).toBeVisible();
  await page.getByRole("button", { name: "계산", exact: true }).first().click();

  await expect(page.getByText(/픽스처 없음.*rebalance/)).toBeVisible();
});

test("늦게 온 응답이 그 사이 고른 값을 덮어쓰지 않는다", async ({ page }) => {
  await mockApi(page);

  // IC 응답을 요청한 시계로 되돌려주되, 3일짜리만 느리게 준다.
  const icFixture = JSON.parse(
    fs.readFileSync(path.join(__dirname, "..", "demo-data", "ic.json"), "utf8"),
  ) as { horizon_days: number };
  await page.route("**/ic/factors**", async (route) => {
    const horizon = Number(new URL(route.request().url()).searchParams.get("horizon_days"));
    if (horizon === 3) await new Promise((r) => setTimeout(r, 1500));
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/json", "access-control-allow-origin": "*" },
      body: JSON.stringify({ ...icFixture, horizon_days: horizon }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("기술적 지표")).toBeVisible();
  await page.locator("nav").getByRole("button", { name: "리서치", exact: true }).click();

  const panel = page.locator("section", { hasText: "팩터 진단 (IC)" }).last();
  await panel.getByRole("button", { name: /어느 신호가 실제로 먹히나/ }).click();
  await expect(panel.getByText(/5일 시계/)).toBeVisible();

  // 느린 3일을 고른 뒤 곧바로 10일로 바꾼다. 3일 응답이 나중에 도착한다.
  await panel.getByRole("button", { name: "3일", exact: true }).click();
  await panel.getByRole("button", { name: "10일", exact: true }).click();
  await expect(panel.getByText(/10일 시계/)).toBeVisible();

  // 3일 응답이 도착하고도 남을 시간. 화면은 10일 그대로여야 한다.
  await page.waitForTimeout(2000);
  await expect(panel.getByText(/10일 시계/)).toBeVisible();
  await expect(panel.getByText(/3일 시계/)).toHaveCount(0);
});
