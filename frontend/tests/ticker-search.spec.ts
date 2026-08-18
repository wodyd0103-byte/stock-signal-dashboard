import { expect, test } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 자동완성을 진짜 브라우저에서 본다.
 *
 * Vitest 쪽(`components/StockSearch.test.tsx`)이 규칙 하나하나를 이미 보고 있으므로
 * 여기서 겹쳐 볼 이유는 없다. 여기서만 볼 수 있는 것은 jsdom 에 없는 것들이다 —
 * 실제 키보드 입력, 목록이 카드 밖으로 떠서 그려지는지, 마우스로 고를 때 blur 가
 * 먼저 닫아버리지 않는지, 그리고 요청이 정말 포커스 시점에 한 번만 나가는지.
 */

const SEARCH = 'input[role="combobox"]';

test("이름 일부를 치면 후보가 뜨고, 골라서 종목을 바꾼다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("삼성");

  const options = page.getByRole("option");
  await expect(options.first()).toContainText("삼성전자");
  await expect(options.first()).toContainText("005930");

  await options.first().click();

  // 고른 종목이 입력에 남고 목록은 닫힌다.
  await expect(search).toHaveValue("005930");
  await expect(page.getByRole("listbox")).toHaveCount(0);
});

test("키보드만으로 고를 수 있다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("삼성");
  await expect(page.getByRole("option").first()).toBeVisible();

  await search.press("ArrowDown");
  const active = page.getByRole("option").first();
  await expect(active).toHaveAttribute("aria-selected", "true");
  await expect(search).toHaveAttribute("aria-activedescendant", (await active.getAttribute("id"))!);

  await search.press("Enter");
  await expect(search).toHaveValue("005930");
});

test("Escape는 목록만 닫는다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("삼성");
  await expect(page.getByRole("option").first()).toBeVisible();

  await search.press("Escape");
  await expect(page.getByRole("listbox")).toHaveCount(0);
  await expect(search).toHaveValue("삼성");
});

test("목록은 카드 위로 떠서 아래 내용을 가린다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("삼성");

  const list = page.getByRole("listbox");
  await expect(list).toBeVisible();

  // 흐름에 끼어들면 헤더 높이가 늘어나 아래 카드가 통째로 밀린다.
  const box = (await list.boundingBox())!;
  const inputBox = (await search.boundingBox())!;
  expect(box.y).toBeGreaterThan(inputBox.y);
  expect(await list.evaluate((el) => getComputedStyle(el).position)).toBe("absolute");
});

test("종목 목록은 검색을 건드리기 전에는 요청하지 않고, 그 뒤로도 한 번만 부른다", async ({
  page,
}) => {
  const calls: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/market/representative-stocks")) calls.push(req.url());
  });

  await mockApi(page);
  await page.goto("/");
  await expect(page.locator(SEARCH)).toBeVisible();
  expect(calls).toHaveLength(0);

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("삼");
  await expect(page.getByRole("option").first()).toBeVisible();

  // 글자를 더 쳐도 다시 부르지 않는다 — 목록은 클라이언트에서 거른다.
  await search.fill("삼성");
  await search.fill("삼성전");
  await expect(page.getByRole("option").first()).toContainText("삼성전자");
  expect(calls).toHaveLength(1);
});

test("유니버스에 없는 종목도 그대로 조회한다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  const requests: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.pathname.includes("/stocks/")) requests.push(url.pathname);
  });

  const search = page.locator(SEARCH);
  await search.click();
  await search.fill("tsla");
  await search.press("Enter");

  await expect.poll(() => requests.some((p) => p.includes("/TSLA/"))).toBe(true);
});
