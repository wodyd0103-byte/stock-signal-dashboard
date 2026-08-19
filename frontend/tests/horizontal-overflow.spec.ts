import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 가로 스크롤 회귀 방지.
 *
 * 좁은 화면에서 페이지가 뷰포트보다 넓어지는 버그가 반복해서 났다. 한 번은
 * 375px에서 문서가 772px로 그려져 화면의 절반이 오른쪽으로 밀려 있었고, 원인은
 * 서로 다른 컴포넌트 네 곳이었다. 카드를 하나 추가할 때마다 다시 날 수 있는
 * 종류라서 자동으로 막는다.
 *
 * jsdom에는 레이아웃 엔진이 없어 이 검사는 진짜 브라우저에서만 의미가 있다.
 *
 * 탭은 반드시 하나씩 눌러가며 재야 한다. 숨은 탭은 display:none 이라 레이아웃을
 * 갖지 않으므로, 기본 화면만 보면 검사한 척만 하게 된다. 실제로 이 순회를 넣기
 * 전까지 포트폴리오 탭에는 375px에서 421px짜리 넘침이 그대로 남아 있었다.
 */

const TABS = ["분석", "포트폴리오", "리서치"] as const;

const VIEWPORTS = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  // lg(1024)는 5열 지표 테이블 복귀와 320px 좌측 레일 등장이 동시에 일어나는
  // 지점이라 따로 본다. 실제로 검토 전까지 아무도 확인하지 않았던 폭이다.
  { name: "lg-boundary", width: 1024, height: 900 },
  { name: "desktop", width: 1440, height: 900 },
];

/** 넘쳤을 때 어떤 요소 때문인지 바로 알 수 있게 같이 수집한다. */
async function measureOverflow(page: Page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const overflow = doc.scrollWidth - doc.clientWidth;
    const offenders: string[] = [];
    if (overflow > 0) {
      document.querySelectorAll("*").forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.right > doc.clientWidth + 1 && rect.width > 20) {
          const cls = (el.className || "").toString().replace(/\s+/g, " ").slice(0, 60);
          offenders.push(`${el.tagName.toLowerCase()}.${cls} → right ${Math.round(rect.right)}`);
        }
      });
    }
    return { overflow, viewportWidth: doc.clientWidth, offenders: offenders.slice(0, 5) };
  });
}

for (const viewport of VIEWPORTS) {
  test(`${viewport.name} (${viewport.width}px): 어느 탭에서도 가로로 넘치지 않는다`, async ({
    page,
  }) => {
    await mockApi(page);
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/");

    // 분석 카드까지 그려진 뒤에 재야 한다. 지표 테이블과 예측 카드가 과거에
    // 넘침을 만든 당사자다.
    await expect(page.getByText("기술적 지표")).toBeVisible();

    for (const tab of TABS) {
      // 상단 검색 버튼에도 "분석"이 있는데, 그건 role=button 이고 이건 role=tab 이라
      // 역할만으로 갈린다(예전에는 nav 안으로 한정해야 했다).
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await expect(page.getByRole("tab", { name: tab, exact: true })).toBeVisible();

      const result = await measureOverflow(page);

      expect(
        result.overflow,
        `[${tab}] 탭에서 문서가 뷰포트(${result.viewportWidth}px)보다 ${result.overflow}px 넓다.\n` +
          `원인 후보:\n${result.offenders.join("\n") || "(없음)"}`,
      ).toBe(0);
    }
  });
}

test("모바일에서 헤더 안의 요소가 화면 밖으로 나가지 않는다", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await expect(page.getByText("기술적 지표")).toBeVisible();

  const strays = await page.evaluate(() => {
    const bar = document.querySelector("header > div");
    if (!bar) return ["헤더를 찾지 못했다"];
    const limit = document.documentElement.clientWidth;
    return [...bar.querySelectorAll("*")]
      .filter((el) => el.getBoundingClientRect().right > limit + 1)
      .map((el) => (el.className || "").toString().slice(0, 40));
  });

  expect(strays, `헤더 요소가 화면 밖으로 나갔다: ${strays.join(", ")}`).toEqual([]);
});
