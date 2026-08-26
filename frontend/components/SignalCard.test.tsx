import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import SignalCard from "./SignalCard";
import type { Signal, SignalScore } from "@/lib/types";

/**
 * 이 카드는 화면에서 제일 먼저 읽히는 자리인데, 표시 규칙이 여섯 군데 흩어져 있다 —
 * 신호별 한글 라벨, 보정점수/원점수 중 무엇을 막대에 쓰는지, ML 확률이 없을 때의
 * 문구, HOLD 일 때 사유 목록을 바꿔 다는 것, 목록 자르기, 막대 폭 클램프.
 * 전부 "틀려도 화면은 멀쩡해 보이는" 종류라 값으로 고정한다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

function makeSignal(overrides: Partial<SignalScore> = {}): SignalScore {
  return {
    signal: "HOLD",
    buy_score: 40,
    sell_score: 30,
    risk_score: 50,
    raw_buy_score: 40,
    raw_sell_score: 30,
    final_buy_score: 40,
    final_sell_score: 30,
    market_regime: "SIDEWAYS",
    ml_up_probability: null,
    relative_strength_score: null,
    liquidity_score: null,
    signal_source: "absolute_regime_ml",
    score_adjustments: [],
    hold_reasons: [],
    buy_score_zone: "중립",
    sell_score_zone: "중립",
    risk_score_zone: "보통",
    score_zone: "관망 구간",
    signal_description: "뚜렷한 방향성이 없습니다.",
    reasons: ["이동평균이 수렴했습니다."],
    buy_factors: [],
    sell_factors: [],
    ...overrides,
  };
}

/** Tile 은 라벨 <p> 와 값 <p> 를 한 div 에 담는다. 라벨로 찾아 값을 읽는다. */
function tileValue(label: string): string {
  const tile = screen.getByText(label).parentElement;
  return tile?.lastElementChild?.textContent ?? "";
}

describe("SignalCard", () => {
  it.each<[Signal, string, string]>([
    ["STRONG BUY", "강력 매수", "🚀"],
    ["BUY", "매수", "📈"],
    ["WEAK BUY", "약매수", "↗"],
    ["HOLD", "관망", "→"],
    ["WEAK SELL", "약매도", "↘"],
    ["SELL", "매도", "📉"],
    ["STRONG SELL", "강력 매도", "⚠"],
  ])("%s는 '%s'로 옮기고 %s 를 붙인다", (signal, korean, emoji) => {
    render(<SignalCard signal={makeSignal({ signal })} />);
    expect(screen.getByText(korean)).toBeTruthy();
    expect(screen.getByText(emoji)).toBeTruthy();
    expect(screen.getByText(signal)).toBeTruthy(); // 칩에는 원문 그대로
  });

  it("막대는 보정 점수를, 타일은 원점수를 쓴다", () => {
    const { container } = render(
      <SignalCard
        signal={makeSignal({
          raw_buy_score: 40,
          final_buy_score: 72,
          raw_sell_score: 20,
          final_sell_score: 33,
        })}
      />,
    );
    expect(container.textContent).toContain("72점");
    expect(container.textContent).toContain("33점");
    expect(tileValue("원 매수")).toBe("40점");
    expect(tileValue("원 매도")).toBe("20점");
  });

  it("ML 확률은 퍼센트로 반올림한다", () => {
    render(<SignalCard signal={makeSignal({ ml_up_probability: 0.734 })} />);
    expect(tileValue("ML 상승확률")).toBe("73%");
  });

  it("ML 확률이 없으면 0%가 아니라 '데이터 부족'", () => {
    // 0 과 null 은 다르다. null 을 0 으로 떨어뜨리면 "상승 가능성 없음"으로 읽힌다.
    render(<SignalCard signal={makeSignal({ ml_up_probability: null })} />);
    expect(tileValue("ML 상승확률")).toBe("데이터 부족");
  });

  it.each([
    [0.62, "62%", true],
    [0.6, "60%", true],
    // 임계값은 원확률이 아니라 반올림한 퍼센트에 걸린다. 0.595 는 59.5% 라
    // 60 미만처럼 보이지만 60% 로 반올림되므로 강조 대상이다.
    [0.595, "60%", true],
    [0.594, "59%", false],
  ])("ML 확률 %s(%s)의 강조 여부는 %s", (probability, shown, highlighted) => {
    render(<SignalCard signal={makeSignal({ ml_up_probability: probability })} />);
    expect(tileValue("ML 상승확률")).toBe(shown);
    // 강조는 클래스로만 드러나서 다른 관측 수단이 없다.
    const tile = screen.getByText("ML 상승확률").parentElement;
    expect(tile?.className.includes("bg-toss-50")).toBe(highlighted);
  });

  it.each([
    [{ relative_strength_score: 3.456 }, "상대 강도", "3.46%"],
    [{ relative_strength_score: null }, "상대 강도", "-"],
    [{ liquidity_score: 67.8 }, "유동성", "68점"],
    [{ liquidity_score: null }, "유동성", "-"],
  ])("%o → %s 타일은 '%s'", (patch, label, expected) => {
    render(<SignalCard signal={makeSignal(patch)} />);
    expect(tileValue(label)).toBe(expected);
  });

  it("시장 국면이 없으면 '-'", () => {
    render(<SignalCard signal={makeSignal({ market_regime: null })} />);
    expect(tileValue("시장 국면")).toBe("-");
  });

  it("HOLD면 제목과 목록을 hold_reasons 로 바꾼다", () => {
    render(
      <SignalCard
        signal={makeSignal({
          signal: "HOLD",
          hold_reasons: ["리스크가 높습니다.", "상대순위가 낮습니다."],
          reasons: ["이동평균 정배열."],
        })}
      />,
    );
    expect(screen.getByText("HOLD 판단 이유")).toBeTruthy();
    expect(screen.getByText("리스크가 높습니다.")).toBeTruthy();
    expect(screen.queryByText("이동평균 정배열.")).toBeNull();
  });

  it("HOLD인데 hold_reasons가 비면 일반 사유로 되돌아간다", () => {
    // 빈 배열이면 목록 자체가 사라져 "왜 관망인지"가 화면에서 통째로 없어진다.
    render(
      <SignalCard
        signal={makeSignal({ signal: "HOLD", hold_reasons: [], reasons: ["이동평균 정배열."] })}
      />,
    );
    expect(screen.getByText("이동평균 정배열.")).toBeTruthy();
  });

  it("HOLD가 아니면 제목은 '판단 이유'이고 reasons 를 쓴다", () => {
    render(
      <SignalCard
        signal={makeSignal({
          signal: "BUY",
          hold_reasons: ["쓰이면 안 되는 사유"],
          reasons: ["RSI 반등."],
        })}
      />,
    );
    expect(screen.getByText("판단 이유")).toBeTruthy();
    expect(screen.getByText("RSI 반등.")).toBeTruthy();
    expect(screen.queryByText("쓰이면 안 되는 사유")).toBeNull();
  });

  it("보정 내역은 5개까지만 보여준다", () => {
    const adjustments = ["하나", "둘", "셋", "넷", "다섯", "여섯", "일곱"];
    render(<SignalCard signal={makeSignal({ score_adjustments: adjustments })} />);

    for (const item of adjustments.slice(0, 5)) {
      expect(screen.getByText(item)).toBeTruthy();
    }
    expect(screen.queryByText("여섯")).toBeNull();
    expect(screen.queryByText("일곱")).toBeNull();
  });

  it("보정 내역이 없으면 그 섹션이 없다", () => {
    render(<SignalCard signal={makeSignal({ score_adjustments: [] })} />);
    expect(screen.queryByText("점수 보정 내역")).toBeNull();
  });

  it("판정과 설명을 함께 보여준다", () => {
    const { container } = render(
      <SignalCard
        signal={makeSignal({ score_zone: "강한 매수 구간", signal_description: "설명." })}
      />,
    );
    expect(container.textContent).toContain("판정: 강한 매수 구간");
    expect(screen.getByText("설명.")).toBeTruthy();
  });

  it("점수가 100을 넘어도 막대는 100%에서 멈춘다", () => {
    // 숫자는 원값 그대로 쓰되 폭만 자른다. 안 자르면 막대가 카드 밖으로 흘러넘친다.
    const { container } = render(<SignalCard signal={makeSignal({ risk_score: 150 })} />);
    const riskBar = container.querySelector<HTMLElement>("div.bg-warn");
    expect(riskBar?.style.width).toBe("100%");
    expect(container.textContent).toContain("150점");
  });

  it("점수가 음수면 막대는 0%", () => {
    const { container } = render(<SignalCard signal={makeSignal({ risk_score: -20 })} />);
    expect(container.querySelector<HTMLElement>("div.bg-warn")?.style.width).toBe("0%");
  });

  it("구간 라벨은 점수 옆에 붙는다", () => {
    const { container } = render(
      <SignalCard signal={makeSignal({ final_buy_score: 82, buy_score_zone: "강한 매수 구간" })} />,
    );
    expect(container.textContent).toContain("82점");
    expect(container.textContent).toContain("· 강한 매수 구간");
  });
});

describe("전환 횟수 배지", () => {
  it("자주 뒤집힌 종목이면 그 사실을 신호 옆에 적는다", () => {
    render(<SignalCard signal={makeSignal()} flipCount={4} />);

    expect(screen.getByText(/최근 30일 4번 뒤집힘/)).toBeTruthy();
  });

  it("한 번뿐이면 적지 않는다", () => {
    // 1회는 그 전환 자체라 셀 것이 없다.
    render(<SignalCard signal={makeSignal()} flipCount={1} />);

    expect(screen.queryByText(/뒤집힘/)).toBeNull();
  });

  it("이력이 없어도 카드는 그대로 그려진다", () => {
    // digest 를 한 번도 안 돌렸으면 0 이다. 그게 고장은 아니다.
    render(<SignalCard signal={makeSignal()} />);

    expect(screen.queryByText(/뒤집힘/)).toBeNull();
  });
});
