import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import FearGreedGauge from "./FearGreedGauge";
import type { MarketSentiment } from "@/lib/types";

/**
 * 게이지는 숫자를 각도와 색으로 바꾼다. 둘 다 화면에서는 "그럴듯해" 보이기만 하면
 * 틀린 걸 눈치채기 어렵다 — 바늘이 5도 어긋나도, 색 경계가 하나 밀려도 그렇다.
 * 그래서 바늘 좌표와 색 경계를 값으로 고정한다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

const CX = 130;
const CY = 130;
const NEEDLE_LENGTH = 82; // r(100) * 0.82

function makeSentiment(overrides: Partial<MarketSentiment> = {}): MarketSentiment {
  return {
    score: 50,
    label: "중립",
    risk_on: true,
    components: [],
    updated_at: "2026-08-18T00:00:00",
    ...overrides,
  };
}

function needle(container: HTMLElement) {
  const line = container.querySelector("line");
  return {
    x: Number(line?.getAttribute("x2")),
    y: Number(line?.getAttribute("y2")),
  };
}

describe("FearGreedGauge", () => {
  it.each([
    [-30, 0],
    [0, 0],
    [50, 50],
    [100, 100],
    [140, 100],
  ])("점수 %i는 %i로 클램프해서 보여준다", (score, shown) => {
    render(<FearGreedGauge sentiment={makeSentiment({ score })} />);
    expect(screen.getByText(String(shown))).toBeTruthy();
  });

  it("0점이면 바늘이 왼쪽 끝을 가리킨다", () => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ score: 0 })} />);
    const { x, y } = needle(container);
    expect(x).toBeCloseTo(CX - NEEDLE_LENGTH, 5);
    expect(y).toBeCloseTo(CY, 5);
  });

  it("50점이면 바늘이 똑바로 위를 가리킨다", () => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ score: 50 })} />);
    const { x, y } = needle(container);
    expect(x).toBeCloseTo(CX, 5);
    expect(y).toBeCloseTo(CY - NEEDLE_LENGTH, 5);
  });

  it("100점이면 바늘이 오른쪽 끝을 가리킨다", () => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ score: 100 })} />);
    const { x, y } = needle(container);
    expect(x).toBeCloseTo(CX + NEEDLE_LENGTH, 5);
    expect(y).toBeCloseTo(CY, 5);
  });

  it("클램프는 바늘에도 걸린다 — 140점이 반원 밖으로 나가면 안 된다", () => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ score: 140 })} />);
    const { x, y } = needle(container);
    expect(x).toBeCloseTo(CX + NEEDLE_LENGTH, 5);
    expect(y).toBeCloseTo(CY, 5);
  });

  it.each([
    [24, "#3182F6"],
    [25, "#84B6FC"],
    [44, "#84B6FC"],
    [45, "#8B95A1"],
    [55, "#8B95A1"],
    [56, "#FF7B82"],
    [74, "#FF7B82"],
    [75, "#F04452"],
  ])("점수 %i의 색은 %s", (score, color) => {
    render(<FearGreedGauge sentiment={makeSentiment({ score })} />);
    // 숫자 자체가 그 색으로 칠해진다. jsdom 은 hex 를 rgb 로 정규화한다.
    expect(screen.getByText(String(score)).getAttribute("style")).toContain(hexToRgb(color));
  });

  it("라벨은 그대로 노출한다", () => {
    render(<FearGreedGauge sentiment={makeSentiment({ label: "극도 공포" })} />);
    expect(screen.getByText("극도 공포")).toBeTruthy();
  });

  it.each([
    [true, "위험선호"],
    [false, "위험회피"],
  ])("risk_on=%s면 '%s'라고 쓴다", (riskOn, text) => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ risk_on: riskOn })} />);
    expect(container.textContent).toContain(text);
  });

  it("구성 요소는 반올림한 점수와 그만큼의 막대 너비로 렌더한다", () => {
    const { container } = render(
      <FearGreedGauge
        sentiment={makeSentiment({
          components: [
            { name: "VIX", raw_value: 24.1, score: 31.6, interpretation: "공포" },
            { name: "환율 변동성", raw_value: 1380, score: 72.4, interpretation: "탐욕" },
          ],
        })}
      />,
    );
    expect(screen.getByText("VIX")).toBeTruthy();
    expect(screen.getByText("32")).toBeTruthy();
    expect(screen.getByText("환율 변동성")).toBeTruthy();
    expect(screen.getByText("72")).toBeTruthy();

    const widths = Array.from(container.querySelectorAll<HTMLElement>("div[style*='width']")).map(
      (el) => el.style.width,
    );
    // 막대 너비는 반올림 전 원값을 쓴다. 반올림한 숫자와 막대가 달라도 되는 자리다.
    expect(widths).toEqual(["31.6%", "72.4%"]);
  });

  it("구성 요소가 없어도 게이지는 그려진다", () => {
    const { container } = render(<FearGreedGauge sentiment={makeSentiment({ components: [] })} />);
    expect(container.querySelector("svg")).toBeTruthy();
    expect(screen.getByText("공포 · 탐욕 지수")).toBeTruthy();
  });
});

function hexToRgb(hex: string): string {
  const value = parseInt(hex.slice(1), 16);
  return `rgb(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255})`;
}
