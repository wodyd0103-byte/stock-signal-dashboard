import { test, expect, type Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 레이아웃이 로딩 중에 얼마나 움직이는지(CLS)를 실제 브라우저에서 잰다.
 *
 * jsdom 에는 레이아웃 엔진이 없어 이 값을 만들 수 없고, Lighthouse 는 CI 에서
 * 돌지 않는다. 그래서 여기서 잰다. 0.1 은 Core Web Vitals 의 "good" 경계다.
 *
 * 이 테스트를 넣기 전 값은 데스크톱 0.273, 모바일 0.386 이었다. 원인은 셋이다:
 *   - 좌측 레일의 관심 목록이 스켈레톤 → 실제 목록으로 바뀌며 높이가 변했다.
 *     위의 발굴 레일이 flex-1 이라 그만큼 줄어들고, 두 목록이 통째로 밀렸다.
 *     (`app/page.tsx`, `components/WatchlistRail.tsx`)
 *   - 분석 스켈레톤이 약 520px 인데 실제 내용은 4,000px 이 넘어, 그 아래
 *     종목 비교 카드가 화면 안에서 밖으로 밀려났다. (`components/AnalysisView.tsx`)
 *   - 검색 버튼의 아이콘이 로딩 스피너(16px)에서 돋보기(18px)로 바뀌면서, 그
 *     2px 때문에 버튼이 다음 줄로 넘어가 폼이 58px 자랐다. 모바일에서만 보였다.
 *     (`components/StockSearch.tsx`)
 */
const BUDGET = 0.1;

async function measureCls(page: Page): Promise<number> {
  await page.addInitScript(() => {
    const w = window as unknown as { __cls: number };
    w.__cls = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { value: number; hadRecentInput: boolean };
        // 사용자 입력 직후 0.5초 안의 변화는 CLS 에서 빠진다. 여기선 입력이
        // 없지만, 규칙을 브라우저와 같게 두려고 그대로 따른다.
        if (!shift.hadRecentInput) w.__cls += shift.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });

  await page.goto("/");
  // 픽스처는 즉시 응답하므로 데이터는 이미 다 들어와 있다. 마지막 리렌더까지
  // 반영된 값을 읽으려고 한 번 더 기다린다.
  await page.getByRole("heading", { level: 2 }).first().waitFor();
  await page.waitForTimeout(1500);

  return page.evaluate(() => (window as unknown as { __cls: number }).__cls);
}

test.describe("로딩이 끝나도 화면이 흔들리지 않는다", () => {
  test("데스크톱", async ({ page }) => {
    // Lighthouse 데스크톱과 같은 크기로 잰다. 폭이 달라지면 좌측 레일이
    // 본문 위로 쌓이거나 옆에 붙어서 다른 값이 나온다.
    await page.setViewportSize({ width: 1350, height: 940 });
    await mockApi(page);

    const cls = await measureCls(page);
    expect(cls, `데스크톱 CLS ${cls.toFixed(3)}`).toBeLessThan(BUDGET);
  });

  test("모바일", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await mockApi(page);

    const cls = await measureCls(page);
    expect(cls, `모바일 CLS ${cls.toFixed(3)}`).toBeLessThan(BUDGET);
  });
});
