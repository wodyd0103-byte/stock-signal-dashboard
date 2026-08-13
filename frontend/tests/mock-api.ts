import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";

const FIXTURES = path.join(__dirname, "fixtures");

/**
 * 경로 -> 픽스처 파일.
 *
 * 부분 문자열이 아니라 정규식으로 맞춘다. `/analysis` 같은 조각으로 매칭하면
 * 종목 분석(`/stocks/005930/analysis`)과 포트폴리오 분석(`/portfolio/analysis`)이
 * 둘 다 걸려서, 먼저 등록된 쪽 픽스처가 반대편으로 흘러간다. 그렇게 섞이면
 * PortfolioPanel 이 주식 분석 객체를 받아 `report.holdings.length` 에서 터지는데,
 * 앱 버그처럼 보여서 추적에 시간을 쓰게 된다.
 *
 * 픽스처는 전부 실제 백엔드 응답을 그대로 받아 둔 것이다. 해석 문장 같은 긴
 * 한글 문자열이 살아 있어야 가로 넘침 회귀를 잡을 수 있다.
 */
const ROUTES: [RegExp, string][] = [
  [/\/stocks\/[^/]+\/analysis\b/, "analysis.json"],
  [/\/stocks\/[^/]+\/backtest\b/, "backtest.json"],
  [/\/market\/sentiment\b/, "sentiment.json"],
  [/\/market\/buy-signals\b/, "buy-signals.json"],
  [/\/watchlist\b/, "watchlist.json"],
  [/\/portfolio\/analysis\b/, "portfolio.json"],
  [/\/retrospective\/summary\b/, "retrospective.json"],
  [/\/ic\/factors\b/, "ic.json"],
];

const cache = new Map<string, string>();

function fixture(file: string): string {
  let body = cache.get(file);
  if (body === undefined) {
    body = fs.readFileSync(path.join(FIXTURES, file), "utf8");
    cache.set(file, body);
  }
  return body;
}

/** 페이지가 백엔드 대신 픽스처를 보게 만든다. 백엔드 없이 실행하기 위한 것. */
export async function mockApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());

    // 다른 오리진(:8000)으로 나가는 요청이라 CORS 헤더가 없으면 브라우저가 막는다.
    const headers = {
      "content-type": "application/json",
      "access-control-allow-origin": "*",
    };

    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }

    const hit = ROUTES.find(([pattern]) => pattern.test(url.pathname));
    if (hit) {
      await route.fulfill({ status: 200, headers, body: fixture(hit[1]) });
      return;
    }

    // 픽스처가 없는 엔드포인트는 실패로 돌려준다. 각 카드가 자체 오류 상태를
    // 그리므로 레이아웃 검사는 계속 유효하고, 조용히 빈 응답을 주는 것보다
    // 무엇이 빠졌는지 드러난다.
    await route.fulfill({
      status: 501,
      headers,
      body: JSON.stringify({ detail: `픽스처 없음: ${url.pathname}` }),
    });
  });
}
