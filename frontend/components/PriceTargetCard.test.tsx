import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import PriceTargetCard from "./PriceTargetCard";
import type { HorizonPrediction, OptimalExit, PriceTarget } from "@/lib/types";

/**
 * 이 카드는 백엔드가 준 숫자를 그대로 찍지 않는다. 세 곳에서 스스로 계산한다:
 * horizon 일수 → 사람이 읽는 기간 이름, horizon 일수 → 개월, 시나리오 가격 →
 * 현재가 대비 등락률. 셋 다 틀려도 숫자는 그럴듯해 보이므로 눈으로는 안 잡힌다.
 *
 * 세 입력이 다 없을 때 아무것도 그리지 않는 것도 계약이다. 빈 카드가 남으면
 * 분석 화면에 이유 없는 여백이 생긴다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

function exit(overrides: Partial<OptimalExit> = {}): OptimalExit {
  return {
    horizon_days: 20,
    horizon_label: "약 1개월",
    target_price: 290000,
    expected_return_pct: 12.84,
    confidence_score: 71,
    risk_adjusted_score: 0.42,
    rationale: "위험 조정 기대수익이 가장 큰 시점입니다.",
    ...overrides,
  };
}

function target(overrides: Partial<PriceTarget> = {}): PriceTarget {
  return {
    horizon_days: 126,
    conservative_price: 240000,
    base_price: 300000,
    optimistic_price: 360000,
    current_price: 250000,
    expected_return_pct: 20,
    confidence_score: 64,
    rationale: "밸류에이션 하단을 보수 시나리오로 잡았습니다.",
    ...overrides,
  };
}

function horizon(overrides: Partial<HorizonPrediction> = {}): HorizonPrediction {
  return {
    horizon_days: 60,
    predicted_price: 280000,
    expected_return_pct: 8.5,
    model_predictions: [],
    confidence_score: 55,
    ...overrides,
  };
}

describe("PriceTargetCard", () => {
  it("셋 다 없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<PriceTargetCard currentPrice={250000} />);
    expect(container.firstChild).toBeNull();
  });

  it("장기 예측이 빈 배열인 것과 없는 것을 같게 다룬다", () => {
    const { container } = render(<PriceTargetCard currentPrice={250000} longTerm={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("있는 것만 그린다 — 매도 시점만 오면 목표가 카드는 없다", () => {
    render(<PriceTargetCard currentPrice={250000} optimalExit={exit()} />);
    expect(screen.getByText("권장 매도 시점")).toBeTruthy();
    expect(screen.queryByText("장기 목표가")).toBeNull();
    expect(screen.queryByText("장기 예측")).toBeNull();
  });

  it.each([
    [60, "약 3개월 후"],
    [120, "약 6개월 후"],
    [90, "90일 후"],
  ])("장기 예측 %i일은 '%s'로 읽힌다", (days, label) => {
    render(<PriceTargetCard currentPrice={250000} longTerm={[horizon({ horizon_days: days })]} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("목표가 카드의 개월 수는 거래일 21일을 한 달로 친다", () => {
    // 126 / 21 = 6. 달력 30일로 나누면 4개월이 되어 백엔드가 잡은 horizon 과
    // 다른 기간을 화면에 적게 된다.
    render(<PriceTargetCard currentPrice={250000} priceTarget={target()} />);
    expect(screen.getByText("약 6개월 후 도달 가능 가격대")).toBeTruthy();
  });

  it("보수·낙관 시나리오의 등락률은 현재가 대비로 직접 계산한다", () => {
    // 240,000 은 현재가 250,000 대비 -4.0%, 360,000 은 +44.0%.
    // 백엔드는 이 둘의 등락률을 보내주지 않는다.
    render(<PriceTargetCard currentPrice={250000} priceTarget={target()} />);
    expect(screen.getByText("-4.0%")).toBeTruthy();
    expect(screen.getByText("+44.0%")).toBeTruthy();
  });

  it("기대수익이 음수면 부호를 붙이지 않고 그대로 음수로 찍는다", () => {
    render(
      <PriceTargetCard currentPrice={250000} optimalExit={exit({ expected_return_pct: -3.25 })} />,
    );
    // "+-3.25%" 가 되면 안 된다.
    expect(screen.getByText("-3.25%")).toBeTruthy();
  });

  it("세 영역이 다 오면 셋 다 그린다", () => {
    render(
      <PriceTargetCard
        currentPrice={250000}
        optimalExit={exit()}
        priceTarget={target()}
        longTerm={[horizon(), horizon({ horizon_days: 120, predicted_price: 310000 })]}
      />,
    );
    expect(screen.getByText("권장 매도 시점")).toBeTruthy();
    expect(screen.getByText("장기 목표가")).toBeTruthy();
    expect(screen.getByText("3개월 · 6개월 후 가격")).toBeTruthy();
    expect(screen.getByText("약 3개월 후")).toBeTruthy();
    expect(screen.getByText("약 6개월 후")).toBeTruthy();
  });
});
