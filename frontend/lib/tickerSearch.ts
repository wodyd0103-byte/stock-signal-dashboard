import type { RepresentativeStock } from "./types";

/**
 * 입력 문자열을 종목 후보로 바꾸는 순수 함수.
 *
 * 목록이 200종목뿐이라 서버에 물어보지 않고 클라이언트에서 거른다. 그래서
 * 디바운스가 없다 — 200개 필터는 한 프레임 안에 끝나므로 지연을 넣으면
 * 반응만 느려진다. 목록이 전 상장사로 커져 서버 검색이 필요해지는 날
 * 그때 디바운스를 붙이면 된다.
 *
 * 순위는 "얼마나 확실한가" 순이다. 티커를 정확히 친 사람은 그 종목을 알고
 * 친 것이므로 언제나 맨 위여야 한다.
 */

const EXACT_TICKER = 0;
const TICKER_PREFIX = 1;
const NAME_PREFIX = 2;
const NAME_CONTAINS = 3;

export const SUGGESTION_LIMIT = 8;

function rank(stock: RepresentativeStock, query: string): number | null {
  const ticker = stock.ticker.toUpperCase();
  const name = stock.name.toUpperCase();

  if (ticker === query) return EXACT_TICKER;
  if (ticker.startsWith(query)) return TICKER_PREFIX;
  if (name.startsWith(query)) return NAME_PREFIX;
  if (name.includes(query)) return NAME_CONTAINS;
  return null;
}

export function matchTickers(
  universe: RepresentativeStock[],
  rawQuery: string,
  limit: number = SUGGESTION_LIMIT,
): RepresentativeStock[] {
  const query = rawQuery.trim().toUpperCase();
  if (!query) return [];

  return (
    universe
      .map((stock, index) => ({ stock, rank: rank(stock, query), index }))
      .filter((entry): entry is { stock: RepresentativeStock; rank: number; index: number } => {
        return entry.rank !== null;
      })
      // 같은 순위 안에서는 원래 순서를 지킨다. 유니버스가 시총 내림차순이라
      // "삼성"을 치면 삼성전자가 삼성바이오로직스보다 먼저 나온다.
      .sort((a, b) => a.rank - b.rank || a.index - b.index)
      .slice(0, limit)
      .map((entry) => entry.stock)
  );
}
