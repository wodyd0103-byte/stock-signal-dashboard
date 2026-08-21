import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./mock-api";

/**
 * 자동 접근성 검사 게이트.
 *
 * **WCAG 2.1 AA 규칙 전부에 대해 위반 0건**을 강제한다. 색 대비도 포함이다 —
 * 예전에는 여기서 `color-contrast` 를 뺐었다. 화면당 48~72개가 걸렸고 원인이
 * 팔레트 토큰이라 시맨틱 변경과 한 PR 에 섞을 수 없었기 때문이다. 지금은 팔레트를
 * 고쳤으므로 제외할 이유가 없다.
 *
 * 스캔 전에 애니메이션을 끝내는 이유: 카드가 페이드인 하는 중에 재면 axe 가
 * 전환 도중의 색을 읽어 실제와 다른 값을 보고한다(배경이 #ffffff 가 아니라
 * #f9fafb 로 잡히는 식). 기준선을 뜰 때 이것 때문에 위반이 3배로 부풀어 보였다.
 *
 * axe 가 못 보는 것(포커스 트랩, 포커스 복귀, 키보드 순회)은 같은 파일 아래쪽에서
 * 직접 검사한다. 자동 검사는 규칙 위반만 보고 "쓸 수 있는지"는 보지 않는다.
 */
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

/** 전환 애니메이션이 끝나기 전에 재면 axe 가 도중의 색을 읽는다. */
async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() =>
    Promise.all(document.getAnimations().map((a) => a.finished.catch(() => {}))),
  );
}

async function scanAll(page: Page, label: string) {
  await settle(page);
  const result = await new AxeBuilder({ page }).withTags(WCAG).analyze();

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

test("분석 화면에 접근성 위반이 없다", async ({ page }) => {
  await openApp(page);
  await scanAll(page, "분석");
});

test("포트폴리오 화면에 접근성 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "포트폴리오" }).click();
  await page.getByRole("button", { name: "포트폴리오 새로고침" }).waitFor();
  await scanAll(page, "포트폴리오");
});

test("리서치 화면에 접근성 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "리서치" }).click();
  await scanAll(page, "리서치");
});

test("설정 대화상자에 접근성 위반이 없다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await scanAll(page, "설정");
});

test("설정 대화상자에 이름이 붙어 있다", async ({ page }) => {
  // 이름 없는 대화상자는 그냥 "대화상자"로만 읽힌다. axe 의 WCAG 규칙집합은
  // 이걸 안 본다(`aria-dialog-name` 은 best-practice 태그) — 그래서 직접 단언한다.
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page.getByRole("dialog", { name: "정보 · 설정" })).toBeVisible();
});

/**
 * axe 가 판정을 포기한 자리를 직접 잰다.
 *
 * `color-contrast` 는 배경을 확신할 수 없으면 위반이 아니라 `incomplete` 로 넘긴다 —
 * 반투명 오버레이 위의 대화상자, 그라디언트 카드, 차트 안의 글씨가 그렇다. 앱 전체에
 * 100건 넘게 그 상태다. 실제로 `--c-warn` 을 예전 값으로 되돌려 보니 대화상자 본문이
 * 미달인데도 스캔은 통과했다. 그래서 그 자리들은 직접 계산해서 못 박는다.
 */
async function contrastOf(page: Page, selector: string): Promise<number> {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) throw new Error(`요소 없음: ${sel}`);

    const parse = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number);
    const over = (fg: number[], bg: number[], a: number) =>
      [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a));
    const lum = ([r, g, b]: number[]) => {
      const f = (v: number) => {
        const x = v / 255;
        return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };

    // 배경 층을 안쪽에서 바깥쪽 순서로 모은 뒤, 바깥에서부터 겹쳐 내려온다.
    // 위로 올라가며 바로 합성하면 뒤에 있어야 할 색이 앞을 덮어쓴다.
    const layers: { rgb: number[]; a: number }[] = [];
    for (let node: Element | null = el; node; node = node.parentElement) {
      const [r, g, b, a = 1] = parse(getComputedStyle(node).backgroundColor);
      if (a > 0) {
        layers.push({ rgb: [r, g, b], a });
        if (a >= 1) break;
      }
    }
    let bg = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i -= 1) bg = over(layers[i].rgb, bg, layers[i].a);

    const [fr, fg, fb, fa = 1] = parse(getComputedStyle(el).color);
    const l1 = lum(over([fr, fg, fb], bg, fa));
    const l2 = lum(bg);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }, selector);
}

test("axe 가 판정 못 하는 대화상자 본문도 AA 를 지킨다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();

  // p 로 한정한다. 같은 클래스가 아이콘(svg)에도 붙어 있어서 그냥 클래스만
  // 쓰면 글씨가 아니라 아이콘을 재게 된다 — 처음에 그래서 주입이 안 잡혔다.
  for (const [label, selector] of [
    ["투자 유의문", "[role=dialog] p[class*='text-warn']"],
    ["외부 앱 안내", "[role=dialog] p[class*='text-toss-700']"],
  ] as const) {
    const ratio = await contrastOf(page, selector);
    expect(ratio, `${label} 대비 ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  }
});

// --- 다크 테마 -----------------------------------------------------------

/**
 * 다크는 따로 돌려야 한다. 색 대비 기준선을 처음 뜰 때 라이트만 재서 48~72개로
 * 봤는데, 다크는 분석 화면 하나가 136개였다. 브랜드색이 고정 hex 라 어두운 배경
 * 위에서 그대로 쓰인 탓이었다 — 라이트만 보면 그 절반이 안 보인다.
 */
test.describe("다크 테마", () => {
  test.use({ colorScheme: "dark" });

  test("다크가 켜져 있다", async ({ page }) => {
    // 이 전제가 깨지면 아래 검사들이 라이트를 두 번 재는 셈이 된다.
    await openApp(page);
    const dark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
    expect(dark).toBe(true);
  });

  test("분석 화면에 접근성 위반이 없다", async ({ page }) => {
    await openApp(page);
    await scanAll(page, "분석(다크)");
  });

  test("포트폴리오 화면에 접근성 위반이 없다", async ({ page }) => {
    await openApp(page);
    await page.getByRole("tab", { name: "포트폴리오" }).click();
    await page.getByRole("button", { name: "포트폴리오 새로고침" }).waitFor();
    await scanAll(page, "포트폴리오(다크)");
  });

  test("리서치 화면에 접근성 위반이 없다", async ({ page }) => {
    await openApp(page);
    await page.getByRole("tab", { name: "리서치" }).click();
    await scanAll(page, "리서치(다크)");
  });

  test("설정 대화상자에 접근성 위반이 없다", async ({ page }) => {
    await openApp(page);
    await page.getByRole("button", { name: "설정" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await scanAll(page, "설정(다크)");
  });
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

// --- 라디오 묶음 ---------------------------------------------------------

test("조회 기간은 radiogroup 으로 노출되고 선택 상태가 읽힌다", async ({ page }) => {
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "조회 기간" });
  await expect(group.getByRole("radio")).toHaveCount(5);

  const oneYear = group.getByRole("radio", { name: "1년" });
  const threeMonths = group.getByRole("radio", { name: "3개월" });
  await expect(oneYear).toHaveAttribute("aria-checked", "true");
  await expect(threeMonths).toHaveAttribute("aria-checked", "false");

  await threeMonths.click();
  await expect(threeMonths).toHaveAttribute("aria-checked", "true");
  await expect(oneYear).toHaveAttribute("aria-checked", "false");
});

test("라디오 묶음도 Tab 한 번에 지나간다", async ({ page }) => {
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "조회 기간" });
  await expect(group.getByRole("radio", { name: "1년" })).toHaveAttribute("tabindex", "0");
  await expect(group.getByRole("radio", { name: "1개월" })).toHaveAttribute("tabindex", "-1");
  await expect(group.getByRole("radio", { name: "3년" })).toHaveAttribute("tabindex", "-1");
});

test("라디오는 위아래 화살표도 받는다", async ({ page }) => {
  // 탭 묶음은 좌우만 받지만(가로 배치) 네이티브 라디오는 네 방향을 다 받는다.
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "조회 기간" });
  const oneYear = group.getByRole("radio", { name: "1년" });
  await oneYear.focus();

  await page.keyboard.press("ArrowDown");
  const threeYears = group.getByRole("radio", { name: "3년" });
  await expect(threeYears).toHaveAttribute("aria-checked", "true");
  await expect(threeYears).toBeFocused();

  await page.keyboard.press("ArrowUp");
  await expect(oneYear).toBeFocused();
});

test("라디오 화살표는 양 끝에서 감기고 Home/End 로 건너뛴다", async ({ page }) => {
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "조회 기간" });
  await group.getByRole("radio", { name: "1개월" }).click();
  await group.getByRole("radio", { name: "1개월" }).focus();

  await page.keyboard.press("ArrowLeft");
  await expect(group.getByRole("radio", { name: "3년" })).toBeFocused();

  await page.keyboard.press("ArrowRight");
  await expect(group.getByRole("radio", { name: "1개월" })).toBeFocused();

  await page.keyboard.press("End");
  await expect(group.getByRole("radio", { name: "3년" })).toBeFocused();

  await page.keyboard.press("Home");
  await expect(group.getByRole("radio", { name: "1개월" })).toBeFocused();
});

test("기간을 화살표로 고르면 그 기간으로 조회한다", async ({ page }) => {
  await openApp(page);
  const requests: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.pathname.includes("/analysis")) requests.push(url.search);
  });

  const group = page.getByRole("radiogroup", { name: "조회 기간" });
  await group.getByRole("radio", { name: "1년" }).focus();
  await page.keyboard.press("ArrowRight"); // 1년 → 3년
  await page.getByRole("button", { name: "분석" }).click();

  await expect.poll(() => requests.some((q) => q.includes("period=3y"))).toBe(true);
});

test("차트 봉 단위도 같은 패턴을 쓴다", async ({ page }) => {
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "봉 단위" });
  await expect(group.getByRole("radio")).toHaveCount(3);

  const daily = group.getByRole("radio", { name: "일" });
  await expect(daily).toHaveAttribute("aria-checked", "true");

  await daily.focus();
  await page.keyboard.press("ArrowRight");
  await expect(group.getByRole("radio", { name: "주" })).toHaveAttribute("aria-checked", "true");
});

test("고를 수 없는 안내는 라디오 묶음 밖에 있다", async ({ page }) => {
  // "분·틱 N/A" 는 버튼이 아니라 설명이다. 묶음 안에 있으면 화살표가
  // 거기서 멈추고 "3개 중 4번째" 같은 소리가 난다.
  await openApp(page);
  const group = page.getByRole("radiogroup", { name: "봉 단위" });
  await expect(group).not.toContainText("N/A");
});

test("포트폴리오의 전략·최적화 묶음도 라디오로 노출된다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "포트폴리오" }).click();
  await page.getByRole("button", { name: "포트폴리오 새로고침" }).waitFor();

  const strategy = page.getByRole("radiogroup", { name: "리밸런싱 전략" });
  await expect(strategy.getByRole("radio")).toHaveCount(3);
  await expect(strategy.getByRole("radio", { name: "신호" })).toHaveAttribute(
    "aria-checked",
    "true",
  );

  const optimize = page.getByRole("radiogroup", { name: "최적화 방식" });
  await expect(optimize.getByRole("radio")).toHaveCount(2);
  await expect(optimize.getByRole("radio", { name: "최대 샤프" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
});

test("리서치의 예측 시계도 라디오로 노출된다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "리서치" }).click();
  await page.getByRole("button", { name: /어느 신호가 실제로 먹히나/ }).click();

  const group = page.getByRole("radiogroup", { name: "예측 시계" });
  await expect(group.getByRole("radio")).toHaveCount(3);
  await expect(group.getByRole("radio", { name: "5일" })).toHaveAttribute("aria-checked", "true");
});

test("보유 종목 삭제 버튼은 어느 종목인지까지 읽힌다", async ({ page }) => {
  await openApp(page);
  await page.getByRole("tab", { name: "포트폴리오" }).click();
  // 이름 없는 "버튼"이 여러 개면 스크린리더 사용자는 무엇을 지우는지 알 수 없다.
  await expect(page.getByRole("button", { name: /삭제$/ }).first()).toBeVisible();
});
