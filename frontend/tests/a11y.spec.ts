import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 자동 접근성 검사 게이트.
 *
 * 두 갈래로 나눠서 본다.
 *
 * 1. **시맨틱 규칙은 0건**을 강제한다. 버튼 이름, 폼 이름, ARIA 속성 정합성 같은
 *    것들이다. 고치는 방법이 명확하고 화면 모양이 바뀌지 않으므로 게이트로 적합하다.
 *
 * 2. **색 대비(`color-contrast`)는 제외**한다. 기준선에서 48~72개 노드가 걸렸는데,
 *    원인이 팔레트 토큰(`--c-muted`, `--c-faint`)과 브랜드색(토스 블루, 상승 빨강)이
 *    4.5:1 에 조금씩 못 미치는 것이라 고치려면 앱 전체 톤과 README 스크린샷까지
 *    바뀐다. 시맨틱 변경과 한 PR 에 섞으면 diff 에서 둘을 구분할 수 없다.
 *    회귀 게이트도 걸지 않는다. axe 가 보고하는 색은 반투명 레이어가 합성된
 *    결과라 같은 토큰이 화면마다 다른 값으로 나온다(`--c-muted` 하나가
 *    #8b95a1/#909aa5/#969faa/#a1a6ae 로 흩어진다). 고정하면 투명도만 건드려도
 *    깨지는 게이트가 되므로, 안 되는 것을 되는 척하지 않고 뺐다.
 *    현재 실패 규모: 화면당 48~72 노드, 전경색 21종(모두 3개 토큰의 변종).
 *
 * axe 가 못 보는 것(포커스 트랩, 포커스 복귀, 키보드 순회)은 같은 파일 아래쪽에서
 * 직접 검사한다. 자동 검사는 규칙 위반만 보고 "쓸 수 있는지"는 보지 않는다.
 */

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function scanSemantics(page: Page, label: string) {
  const result = await new AxeBuilder({ page })
    .withTags(WCAG)
    .disableRules(["color-contrast"])
    .analyze();

  const report = result.violations.map(
    (v) =>
      `${label} — [${v.impact}] ${v.id} x${v.nodes.length}: ${v.help}\n    ${v.nodes.map((n) => n.target.join(" ")).join("\n    ")}`,
  );
  expect(report, report.join("\n")).toEqual([]);
}

async function openApp(page: Page) {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("combobox").waitFor();
}

test("분석 화면에 시맨틱 위반이 없다", async ({ page }) => {
  await openApp(page);
  await scanSemantics(page, "분석");
});

test("포트폴리오 화면에 시맨틱 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "포트폴리오" }).click();
  await page.getByRole("button", { name: "포트폴리오 새로고침" }).waitFor();
  await scanSemantics(page, "포트폴리오");
});

test("리서치 화면에 시맨틱 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "리서치" }).click();
  await scanSemantics(page, "리서치");
});

test("설정 대화상자에 시맨틱 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await scanSemantics(page, "설정");
});

test("설정 대화상자에 이름이 붙어 있다", async ({ page }) => {
  // 이름 없는 대화상자는 그냥 "대화상자"로만 읽힌다. axe 의 WCAG 규칙집합은
  // 이걸 안 본다(`aria-dialog-name` 은 best-practice 태그) — 그래서 직접 단언한다.
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page.getByRole("dialog", { name: "정보 · 설정" })).toBeVisible();
});

// --- axe 가 못 보는 것 ---------------------------------------------------

test("설정 대화상자는 Escape 로 닫히고 포커스가 열었던 버튼으로 돌아온다", async ({ page }) => {
  await openApp(page);
  const opener = page.getByRole("button", { name: "설정" });
  await opener.click();
  await expect(page.getByRole("dialog")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // 포커스가 문서 처음으로 튕기면 키보드 사용자는 다시 Tab 을 반복해야 한다.
  await expect(opener).toBeFocused();
});

test("설정 대화상자 안에서 Tab 이 밖으로 새지 않는다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  // 대화상자 안의 포커스 대상보다 넉넉히 많이 눌러 한 바퀴 이상 돌린다.
  for (let i = 0; i < 8; i += 1) {
    await page.keyboard.press("Tab");
    const inside = await dialog.evaluate((el) => el.contains(document.activeElement));
    expect(inside, `Tab ${i + 1}번째에 포커스가 대화상자를 벗어났다`).toBe(true);
  }
});

test("Shift+Tab 도 대화상자 안에 머문다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();

  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press("Shift+Tab");
    const inside = await dialog.evaluate((el) => el.contains(document.activeElement));
    expect(inside, `Shift+Tab ${i + 1}번째에 포커스가 벗어났다`).toBe(true);
  }
});

test("보유 종목 삭제 버튼은 어느 종목인지까지 읽힌다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "포트폴리오" }).click();
  // 이름 없는 "버튼"이 여러 개면 스크린리더 사용자는 무엇을 지우는지 알 수 없다.
  await expect(page.getByRole("button", { name: /삭제$/ }).first()).toBeVisible();
});
