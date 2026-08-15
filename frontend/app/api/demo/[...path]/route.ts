import { NextResponse } from "next/server";
import analysis from "@/demo-data/analysis.json";
import backtest from "@/demo-data/backtest.json";
import buySignals from "@/demo-data/buy-signals.json";
import ic from "@/demo-data/ic.json";
import portfolio from "@/demo-data/portfolio.json";
import retrospective from "@/demo-data/retrospective.json";
import sentiment from "@/demo-data/sentiment.json";
import watchlist from "@/demo-data/watchlist.json";

/**
 * 백엔드 없이 앱을 배포하기 위한 데모 API.
 *
 * Vercel에는 Next.js 앱만 올라간다. FastAPI는 pykrx·yfinance로 외부 시세를
 * 받아오고 SQLite에 쓰기 때문에 같이 올릴 수 없고, 그렇다고 프론트만 올리면
 * 링크를 연 사람은 카드마다 "백엔드 서버에 연결할 수 없습니다"만 보게 된다.
 *
 * 그래서 `demo-data/`에 받아둔 **실제 백엔드 응답**을 그대로 돌려준다. 숫자와
 * 해석 문장이 진짜라서 화면이 제대로 채워지고, 값이 고정이라는 사실은 화면
 * 상단 배너로 알린다(`components/DemoBanner.tsx`).
 *
 * `NEXT_PUBLIC_API_BASE_URL=/api/demo` 로 배포하면 `lib/api.ts`가 여기를 본다.
 * 경로 모양은 FastAPI와 같아야 하므로 아래 정규식도 백엔드 라우터를 따른다.
 */

// tests/mock-api.ts 와 같은 순서·같은 규칙. 부분 문자열이 아니라 정규식으로
// 맞춘다. `/analysis`로 자르면 종목 분석과 포트폴리오 분석이 함께 걸린다.
const ROUTES: [RegExp, unknown][] = [
  [/^stocks\/[^/]+\/analysis$/, analysis],
  [/^stocks\/[^/]+\/backtest$/, backtest],
  [/^market\/sentiment$/, sentiment],
  [/^market\/buy-signals$/, buySignals],
  [/^watchlist$/, watchlist],
  [/^portfolio\/analysis$/, portfolio],
  [/^retrospective\/summary$/, retrospective],
  [/^ic\/factors$/, ic],
];

/** 캡처해두지 않은 조회. 오류 대신 빈 목록을 주어 화면이 빈 상태를 그리게 한다. */
const EMPTY: [RegExp, unknown][] = [
  [/^surge\/scan$/, { items: [], market: "KR", updated_at: null }],
  [/^market\/compare$/, { items: [], error: "데모 데이터에는 종목 비교 결과가 없습니다." }],
];

function json(body: unknown, status = 200) {
  // 값이 고정이므로 캐시해도 되지만, 데모가 낡은 화면을 들고 있는 것보다
  // 매번 같은 응답을 주는 편이 헷갈리지 않는다.
  return NextResponse.json(body, { status, headers: { "cache-control": "no-store" } });
}

export async function GET(_request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");

  const hit = ROUTES.find(([pattern]) => pattern.test(path));
  if (hit) return json(hit[1]);

  const empty = EMPTY.find(([pattern]) => pattern.test(path));
  if (empty) return json(empty[1]);

  return json({ detail: `데모 데이터가 없는 경로입니다: /${path}` }, 404);
}

/** 쓰기는 받지 않는다. 데모에 저장할 곳이 없다는 사실을 그대로 알린다. */
function readOnly() {
  return json({ detail: "데모에서는 저장·삭제가 되지 않습니다. 값은 고정입니다." }, 405);
}

export const POST = readOnly;
export const PUT = readOnly;
export const PATCH = readOnly;
export const DELETE = readOnly;
