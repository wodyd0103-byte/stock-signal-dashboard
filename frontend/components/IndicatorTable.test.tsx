import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import IndicatorTable from "./IndicatorTable";
import type { IndicatorDetail } from "@/lib/types";

/**
 * 표 자체는 단순한데 값 표시 규칙이 세 군데 숨어 있다 — 기여도 부호 접두사,
 * null 값의 대체 문자, 영향(매수/매도/그 외)에 따른 색. 셋 다 틀려도 화면은
 * 멀쩡해 보이고 숫자만 틀린다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

function makeIndicator(overrides: Partial<IndicatorDetail> = {}): IndicatorDetail {
  return {
    name: "RSI",
    value: 58.2,
    interpretation: "중립 구간입니다.",
    influence: "관망",
    contribution: 0,
    ...overrides,
  };
}

describe("IndicatorTable", () => {
  it("지표마다 이름·값·해석을 한 행씩 렌더한다", () => {
    render(
      <IndicatorTable
        indicators={[
          makeIndicator({ name: "RSI", value: 58.2, interpretation: "중립 구간입니다." }),
          makeIndicator({ name: "MACD", value: -1.4, interpretation: "약세 전환." }),
        ]}
      />,
    );
    expect(screen.getByText("RSI")).toBeTruthy();
    expect(screen.getByText("58.2")).toBeTruthy();
    expect(screen.getByText("중립 구간입니다.")).toBeTruthy();
    expect(screen.getByText("MACD")).toBeTruthy();
    expect(screen.getByText("-1.4")).toBeTruthy();
    expect(screen.getByText("약세 전환.")).toBeTruthy();
  });

  it("값이 없으면 빈칸이 아니라 '-'", () => {
    render(<IndicatorTable indicators={[makeIndicator({ value: null })]} />);
    expect(screen.getByText("-")).toBeTruthy();
  });

  it.each([
    [7, "+7", "text-up"],
    [0, "0", "text-muted"],
    [-7, "-7", "text-down"],
  ])("기여도 %i는 '%s'로 찍고 %s 색을 쓴다", (contribution, text, toneClass) => {
    render(<IndicatorTable indicators={[makeIndicator({ contribution })]} />);
    // 양수에만 '+'를 붙인다. 음수는 숫자가 이미 부호를 갖고 있어 '+-7'이 되면 안 된다.
    // 값 셀도 text-right·tabular 를 갖고 있어서 선택자 대신 찍힌 텍스트로 찾는다.
    expect(screen.getByText(text).className).toContain(toneClass);
  });

  it.each([
    ["매수", "text-up"],
    ["매도", "text-down"],
    ["관망", "text-sub"],
  ])("영향 '%s'는 %s 톤", (influence, toneClass) => {
    render(<IndicatorTable indicators={[makeIndicator({ influence })]} />);
    expect(screen.getByText(influence).className).toContain(toneClass);
  });

  it("지표가 없으면 행 없이 껍데기만 렌더한다", () => {
    render(<IndicatorTable indicators={[]} />);
    expect(screen.getByText("현재 값과 신호 기여도")).toBeTruthy();
  });
});
