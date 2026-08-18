import { describe, expect, it } from "vitest";
import { matchTickers, SUGGESTION_LIMIT } from "./tickerSearch";
import type { RepresentativeStock } from "./types";

/**
 * 매칭 규칙은 화면 없이 검사한다. 정렬이 한 칸 어긋나면 "삼성"을 쳤을 때
 * 삼성전자가 두 번째로 밀리는 식으로 조용히 나빠지는데, 렌더 테스트에서는
 * 그게 목록 순서 하나로만 보여서 원인을 짚기 어렵다.
 */

// 실제 유니버스처럼 시총 내림차순이다. 이 순서가 동순위 정렬의 기준이 된다.
const UNIVERSE: RepresentativeStock[] = [
  { name: "삼성전자", ticker: "005930", market: "KR" },
  { name: "SK하이닉스", ticker: "000660", market: "KR" },
  { name: "삼성바이오로직스", ticker: "207940", market: "KR" },
  { name: "삼성SDI", ticker: "006400", market: "KR" },
  { name: "카카오", ticker: "035720", market: "KR" },
  { name: "Apple", ticker: "AAPL", market: "US" },
  { name: "Microsoft", ticker: "MSFT", market: "US" },
];

const tickersOf = (query: string, limit?: number) =>
  matchTickers(UNIVERSE, query, limit).map((stock) => stock.ticker);

describe("matchTickers", () => {
  it.each(["", "   "])("빈 입력(%j)에는 후보가 없다", (query) => {
    expect(matchTickers(UNIVERSE, query)).toEqual([]);
  });

  it("한글 이름의 일부로 찾는다", () => {
    expect(tickersOf("삼성")).toEqual(["005930", "207940", "006400"]);
  });

  it("동순위는 유니버스 순서를 지킨다 — 시총 큰 종목이 먼저", () => {
    // 셋 다 '삼성'으로 시작하므로 순위가 같다. 삼성전자가 목록에서 앞이라 먼저다.
    expect(matchTickers(UNIVERSE, "삼성")[0].name).toBe("삼성전자");
  });

  it("이름 중간에 걸려도 찾는다", () => {
    expect(tickersOf("바이오")).toEqual(["207940"]);
  });

  it("티커를 정확히 치면 그 종목이 맨 위", () => {
    // '00'으로 시작하는 티커가 여럿이지만 정확히 친 것이 이긴다.
    expect(tickersOf("000660")[0]).toBe("000660");
  });

  it("티커 앞자리로도 찾는다", () => {
    expect(tickersOf("0059")).toEqual(["005930"]);
  });

  it("영문 티커는 대소문자를 가리지 않는다", () => {
    expect(tickersOf("aapl")).toEqual(["AAPL"]);
    expect(tickersOf("AAPL")).toEqual(["AAPL"]);
  });

  it("영문 이름도 대소문자를 가리지 않는다", () => {
    expect(tickersOf("microsoft")).toEqual(["MSFT"]);
  });

  it("앞뒤 공백은 무시한다", () => {
    expect(tickersOf("  카카오  ")).toEqual(["035720"]);
  });

  it("이름 앞부분이 뒷부분보다 먼저 나온다", () => {
    const universe: RepresentativeStock[] = [
      { name: "네오위즈홀딩스", ticker: "042420", market: "KR" },
      { name: "위즈코프", ticker: "038620", market: "KR" },
    ];
    // 이름이 '위즈'로 시작하는 쪽이 목록에서는 뒤인데도 먼저 나와야 한다.
    expect(matchTickers(universe, "위즈").map((s) => s.ticker)).toEqual(["038620", "042420"]);
  });

  it("맞는 게 없으면 빈 배열", () => {
    expect(matchTickers(UNIVERSE, "없는회사")).toEqual([]);
  });

  it("개수를 제한한다", () => {
    const many: RepresentativeStock[] = Array.from({ length: 30 }, (_, i) => ({
      name: `테스트${i}`,
      ticker: String(i).padStart(6, "0"),
      market: "KR" as const,
    }));
    expect(matchTickers(many, "테스트")).toHaveLength(SUGGESTION_LIMIT);
    expect(matchTickers(many, "테스트", 3)).toHaveLength(3);
  });

  it("유니버스가 비어 있어도 터지지 않는다", () => {
    expect(matchTickers([], "삼성")).toEqual([]);
  });
});
