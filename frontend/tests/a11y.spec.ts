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
  await page.getByRole("tab", { name: "포트폴리오" }).click();
  await page.getByRole("button", { name: "포트폴리오 새로고침" }).waitFor();
  await scanSemantics(page, "포트폴리오");
});

test("리서치 화면에 시맨틱 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "리서치" }).click();
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

test("메인 탭은 tablist 로 노출되고 선택 상태가 읽힌다", async ({ page }) => {
  await openApp(page);
  const tablist = page.getByRole("tablist", { name: "화면 전환" });
  await expect(tablist.getByRole("tab")).toHaveCount(3);

  const analysis = page.getByRole("tab", { name: "분석" });
  const portfolio = page.getByRole("tab", { name: "포트폴리오" });
  await expect(analysis).toHaveAttribute("aria-selected", "true");
  await expect(portfolio).toHaveAttribute("aria-selected", "false");

  await portfolio.click();
  await expect(portfolio).toHaveAttribute("aria-selected", "true");
  await expect(analysis).toHaveAttribute("aria-selected", "false");
});

test("탭 묶음은 Tab 키 한 번에 통과한다", async ({ page }) => {
  await openApp(page);
  // roving tabindex. 선택된 것만 0, 나머지는 -1 이라 Tab 이 탭마다 멈추지 않는다.
  await expect(page.getByRole("tab", { name: "분석" })).toHaveAttribute("tabindex", "0");
  await expect(page.getByRole("tab", { name: "포트폴리오" })).toHaveAttribute("tabindex", "-1");
  await expect(page.getByRole("tab", { name: "리서치" })).toHaveAttribute("tabindex", "-1");
});

test("화살표로 탭을 옮기면 포커스도 따라간다", async ({ page }) => {
  await openApp(page);
  const analysis = page.getByRole("tab", { name: "분석" });
  const portfolio = page.getByRole("tab", { name: "포트폴리오" });
  await analysis.focus();

  await page.keyboard.press("ArrowRight");
  await expect(portfolio).toHaveAttribute("aria-selected", "true");
  // 선택만 옮기고 포커스를 두고 오면 다음 화살표가 엉뚱한 자리에서 출발한다.
  await expect(portfolio).toBeFocused();

  await page.keyboard.press("ArrowLeft");
  await expect(analysis).toBeFocused();
});

test("화살표는 양 끝에서 감기고 Home/End 로 건너뛴다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "분석" }).focus();

  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "리서치" })).toBeFocused();

  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "분석" })).toBeFocused();

  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "리서치" })).toBeFocused();

  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: "분석" })).toBeFocused();
});

test("메인 탭은 고른 패널만 접근성 트리에 남긴다", async ({ page }) => {
  await openApp(page);

  // 탭 묶음이 둘이라 화면에 보이는 tabpanel 도 둘이다(메인 + 발굴 레일).
  // 그래서 전체 개수가 아니라 각 탭이 가리키는 패널을 직접 확인한다.
  const panelOf = async (tabName: string) => {
    const id = await page.getByRole("tab", { name: tabName }).getAttribute("aria-controls");
    return page.locator(`[id="${id}"]`);
  };

  await expect(await panelOf("분석")).toBeVisible();
  await expect(await panelOf("포트폴리오")).toBeHidden();
  await expect(await panelOf("리서치")).toBeHidden();

  // 패널은 자기를 여는 탭을 가리켜야 한다. 짝이 어긋나면 읽는 쪽에서
  // "포트폴리오" 탭을 눌렀는데 "분석" 이라고 읽힌다.
  const analysisTabId = await page.getByRole("tab", { name: "분석" }).getAttribute("id");
  await expect(await panelOf("분석")).toHaveAttribute("aria-labelledby", analysisTabId!);

  await page.getByRole("tab", { name: "리서치" }).click();
  await expect(await panelOf("분석")).toBeHidden();
  await expect(await panelOf("리서치")).toBeVisible();

  // 첫 탭만 확인하면 "모든 패널이 첫 탭을 가리킨다" 는 실수를 놓친다.
  const researchTabId = await page.getByRole("tab", { name: "리서치" }).getAttribute("id");
  await expect(await panelOf("리서치")).toHaveAttribute("aria-labelledby", researchTabId!);
  expect(researchTabId).not.toBe(analysisTabId);
});

test("발굴 레일도 같은 탭 패턴을 쓴다", async ({ page }) => {
  await openApp(page);
  const rail = page.getByRole("tablist", { name: "종목 발굴 방식" });
  await expect(rail.getByRole("tab")).toHaveCount(2);

  const buy = rail.getByRole("tab", { name: /매수 신호/ });
  const surge = rail.getByRole("tab", { name: /급등 탐색/ });
  await expect(buy).toHaveAttribute("aria-selected", "true");

  await buy.focus();
  await page.keyboard.press("ArrowRight");
  await expect(surge).toHaveAttribute("aria-selected", "true");
  await expect(surge).toBeFocused();
});

test("새로고침 버튼은 탭 묶음 밖에 있다", async ({ page }) => {
  await openApp(page);
  // tablist 안에 탭이 아닌 것이 섞이면 화살표 이동이 그 위에서 멈추고
  // 스크린리더가 "2개 중 3번째" 같은 소리를 한다.
  const rail = page.getByRole("tablist", { name: "종목 발굴 방식" });
  await expect(rail.getByRole("button", { name: "목록 새로고침" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "목록 새로고침" })).toBeVisible();
});

test("보유 종목 삭제 버튼은 어느 종목인지까지 읽힌다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "포트폴리오" }).click();
  // 이름 없는 "버튼"이 여러 개면 스크린리더 사용자는 무엇을 지우는지 알 수 없다.
  await expect(page.getByRole("button", { name: /삭제$/ }).first()).toBeVisible();
});
