import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import RiskCard from "./RiskCard";
import type { RiskResponse } from "@/lib/types";

/**
 * 이 카드가 하는 일은 점수를 등급으로 바꾸는 것 하나다. 경계값(30/60/80)이
 * 어긋나면 화면에 잘못된 등급이 뜨는데, 숫자는 그대로라서 눈으로는 안 잡힌다.
 * 그래서 경계 양쪽을 전부 고정한다.
 *
 * vitest.config.mts 에 globals 가 없어서 RTL 자동 cleanup 이 등록되지 않는다
 * (RTL 은 전역 afterEach 가 있을 때만 건다). 직접 부르지 않으면 이전 테스트의
 * DOM 이 남아 getBy* 가 중복으로 터진다.
 */
afterEach(cleanup);

function makeRisk(overrides: Partial<RiskResponse> = {}): RiskResponse {
  return {
    ticker: "005930",
    period: "1y",
    risk_score: 42,
    risk_level: "보통",
    metrics: [
      { name: "연변동성", value: 24.3, interpretation: "평균 수준", contribution: 10 },
      { name: "최대낙폭", value: -18.2, interpretation: "제한적", contribution: 5 },
    ],
    reasons: ["변동성이 평균 수준입니다."],
    ...overrides,
  };
}

describe("RiskCard", () => {
  it.each([
    [0, "낮음"],
    [30, "낮음"],
    [31, "보통"],
    [60, "보통"],
    [61, "높음"],
    [80, "높음"],
    [81, "매우 높음"],
    [100, "매우 높음"],
  ])("점수 %i는 '%s' 등급", (score, label) => {
    render(<RiskCard risk={makeRisk({ risk_score: score })} />);
    expect(screen.getByText(String(score))).toBeTruthy();
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("지표를 모두 렌더하고 값은 문자열로 찍는다", () => {
    render(
      <RiskCard
        risk={makeRisk({
          metrics: [
            { name: "연변동성", value: 24.3, interpretation: "", contribution: 0 },
            // boolean 도 들어온다(RiskMetric.value 는 number | string | boolean).
            // String() 없이 그냥 넣으면 React 가 조용히 아무것도 안 그린다.
            { name: "추세 하락", value: false, interpretation: "", contribution: 0 },
          ],
        })}
      />,
    );
    expect(screen.getByText("연변동성")).toBeTruthy();
    expect(screen.getByText("24.3")).toBeTruthy();
    expect(screen.getByText("추세 하락")).toBeTruthy();
    expect(screen.getByText("false")).toBeTruthy();
  });

  it("사유는 4개까지만 보여준다", () => {
    const reasons = ["하나", "둘", "셋", "넷", "다섯", "여섯"];
    render(<RiskCard risk={makeRisk({ reasons })} />);

    for (const reason of reasons.slice(0, 4)) {
      expect(screen.getByText(reason)).toBeTruthy();
    }
    expect(screen.queryByText("다섯")).toBeNull();
    expect(screen.queryByText("여섯")).toBeNull();
  });

  it("사유가 없으면 사유 영역 자체가 없다", () => {
    const { container } = render(<RiskCard risk={makeRisk({ reasons: [] })} />);
    expect(container.querySelector("ul")).toBeNull();
  });
});
