import { expect, test } from "@playwright/test";

/**
 * 백엔드 없이 배포하기 위한 데모 API(`app/api/demo`). 배포본에서 화면이 비면
 * 링크를 연 사람에게는 그게 앱의 전부라서, 경로 모양이 어긋나는 것을 여기서 막는다.
 *
 * 브라우저를 띄우지 않고 요청만 보낸다. `NEXT_PUBLIC_DEMO` 없이 빌드해도 라우트
 * 핸들러 자체는 존재하므로 일반 실행에서도 그대로 검사된다.
 */

const READS = [
  "/api/demo/stocks/005930/analysis",
  "/api/demo/stocks/005930/backtest",
  "/api/demo/market/sentiment",
  "/api/demo/market/buy-signals",
  "/api/demo/watchlist",
  "/api/demo/portfolio/analysis",
  "/api/demo/retrospective/summary",
  "/api/demo/ic/factors",
  "/api/demo/surge/scan",
  "/api/demo/market/compare",
];

test("데모 API가 화면이 쓰는 조회를 모두 200으로 돌려준다", async ({ request }) => {
  for (const path of READS) {
    const res = await request.get(path);
    expect(res.status(), `${path}가 200이 아니다`).toBe(200);
    expect(await res.json()).toBeTruthy();
  }
});

test("종목 분석과 포트폴리오 분석이 서로 다른 데이터를 준다", async ({ request }) => {
  // 경로를 부분 문자열로 맞추면 둘이 섞인다. 실제로 예전에 겪은 실수라 못박아 둔다.
  const stock = await (await request.get("/api/demo/stocks/005930/analysis")).json();
  const portfolio = await (await request.get("/api/demo/portfolio/analysis")).json();

  expect(stock).toHaveProperty("indicators");
  expect(portfolio).toHaveProperty("holdings");
});

test("데모에서는 쓰기가 405로 막히고 이유를 알려준다", async ({ request }) => {
  const res = await request.post("/api/demo/watchlist", { data: { ticker: "005930" } });
  expect(res.status()).toBe(405);
  expect((await res.json()).detail).toContain("데모");
});

test("데이터가 없는 경로는 404와 경로명을 돌려준다", async ({ request }) => {
  const res = await request.get("/api/demo/nope/nothing");
  expect(res.status()).toBe(404);
  expect((await res.json()).detail).toContain("/nope/nothing");
});
