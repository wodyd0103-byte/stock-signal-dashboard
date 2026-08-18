import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * demo-data/의 응답을 정적 파일로 펼쳐 `public/api/demo/` 아래에 놓는다.
 *
 * 배포본에는 백엔드가 없다. 예전에는 Next 라우트 핸들러가 이 역할을 했는데,
 * GitHub Pages는 정적 파일만 서빙하므로 서버가 필요 없는 형태로 바꿨다.
 * 파일 이름에 확장자를 붙이지 않는 이유는 앱이 부르는 경로 그대로여야 하기
 * 때문이다(`/api/demo/market/sentiment`). `fetch(...).json()`은 Content-Type을
 * 보지 않고 본문을 파싱하므로 확장자가 없어도 동작한다.
 *
 * 쿼리스트링(`?period=1y`, `?force_refresh=true`)은 정적 서버가 무시하므로
 * 같은 파일이 돌아온다. 데모에서는 값이 고정이라 문제되지 않는다.
 *
 * 이 스크립트는 `npm run build`의 prebuild로 자동 실행된다. 결과물은
 * gitignore 대상이다 — 소스는 demo-data/ 하나뿐이어야 한다.
 */

const here = dirname(fileURLToPath(import.meta.url));
const DEMO_DATA = join(here, "..", "demo-data");
const OUT = join(here, "..", "public", "api", "demo");

/** 데모에 데이터가 있는 종목. 다른 종목은 404가 나고 앱이 그 사실을 화면에 띄운다. */
const DEMO_TICKER = "005930";

/** 앱이 부르는 경로 → demo-data 파일. 없는 응답은 아래 EMPTY에서 만든다. */
const FILES = [
  [`stocks/${DEMO_TICKER}/analysis`, "analysis.json"],
  [`stocks/${DEMO_TICKER}/backtest`, "backtest.json"],
  ["market/sentiment", "sentiment.json"],
  ["market/buy-signals", "buy-signals.json"],
  // 검색 자동완성이 거를 종목 목록. 없으면 데모에서 자동완성만 조용히 죽는다.
  ["market/representative-stocks", "representative-stocks.json"],
  ["watchlist", "watchlist.json"],
  ["portfolio/analysis", "portfolio.json"],
  ["retrospective/summary", "retrospective.json"],
  ["ic/factors", "ic.json"],
];

/** 캡처해두지 않은 조회. 오류 대신 빈 결과를 주어 화면이 빈 상태를 그리게 한다. */
const EMPTY = [
  ["surge/scan", { items: [], market: "KR", updated_at: null }],
  ["market/compare", { items: [], error: "데모에는 종목 비교 결과가 없습니다." }],
];

async function write(route, body) {
  const target = join(OUT, route);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, body, "utf8");
}

await rm(OUT, { recursive: true, force: true });

for (const [route, file] of FILES) {
  await write(route, await readFile(join(DEMO_DATA, file), "utf8"));
}

for (const [route, body] of EMPTY) {
  await write(route, JSON.stringify(body));
}

// CSV 내보내기 링크는 데모에 파일이 없어 404가 난다. 감추지 않는다 —
// 데모가 실제보다 완전한 척하는 것보다 낫다.

console.log(`demo api: ${FILES.length + EMPTY.length} routes -> public/api/demo`);
