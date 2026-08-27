import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import SupplyDemandCard from "./SupplyDemandCard";
import type { SectorStrength, SupplyDemand } from "@/lib/types";

/**
 * 이 카드에서 깨져도 눈에 안 띄는 것은 색이다. 한국 시장 관례로 순매수가
 * 빨강(`text-up`), 순매도가 파랑(`text-down`)인데, 토큰 이름만 보면 "up = 초록,
 * 오르면 초록"이라는 서구 관례로 되돌리기 쉽다. 되돌려도 화면은 멀쩡해 보이고
 * 숫자도 맞다 — 읽는 사람만 반대로 읽는다. 그래서 클래스로 고정한다.
 *
 * 20일 칸이 회색인 것도 의도다. 5일과 20일이 같은 채도로 있으면 어느 쪽이
 * 최근 흐름인지 구분이 안 된다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

function sd(overrides: Partial<SupplyDemand> = {}): SupplyDemand {
  return {
    ticker: "005930",
    foreign_5d: 120000,
    foreign_20d: -450000,
    inst_5d: -30000,
    inst_20d: 210000,
    korean_flow_score: 62.4,
    buying: true,
    summary: "외국인이 5일 연속 순매수했습니다.",
    foreign_hold_ratio: 53.27,
    ...overrides,
  };
}

function sector(overrides: Partial<SectorStrength> = {}): SectorStrength {
  return {
    ticker: "005930",
    stock_return_20d: 8.2,
    peer_median_20d: 3.1,
    sector_rs: 5.1,
    percentile: 78,
    score: 71,
    peer_count: 12,
    summary: "업종 중앙값을 웃돕니다.",
    ...overrides,
  };
}

/**
 * 값 텍스트가 들어 있는 <p> 의 클래스.
 *
 * 부호를 붙여서 찾는다. 부호와 숫자가 형제 텍스트 노드라서 RTL 이 둘을 이어
 * 하나로 본다 — "120,000" 만으로는 안 잡히고 "+120,000" 이어야 한다.
 */
function toneOf(text: string): string {
  const el = screen.getByText(text).closest("p");
  if (!el) throw new Error(`${text} 를 담은 p 가 없다`);
  return el.className;
}

describe("SupplyDemandCard", () => {
  it("5일 순매수는 빨강, 순매도는 파랑 — 한국 관례를 따른다", () => {
    render(<SupplyDemandCard sd={sd({ foreign_5d: 120000, inst_5d: -30000 })} />);
    expect(toneOf("+120,000")).toContain("text-up");
    expect(toneOf("-30,000")).toContain("text-down");
  });

  it("20일 칸은 부호와 무관하게 회색이다", () => {
    render(<SupplyDemandCard sd={sd({ foreign_20d: -450000, inst_20d: 210000 })} />);
    expect(toneOf("-450,000")).toContain("text-muted");
    expect(toneOf("+210,000")).toContain("text-muted");
    expect(toneOf("+210,000")).not.toContain("text-up");
  });

  it("양수에만 + 를 붙이고 음수는 그대로 둔다", () => {
    render(<SupplyDemandCard sd={sd({ foreign_5d: 120000, inst_5d: -30000 })} />);
    // "+-30,000" 이 되면 안 된다.
    expect(screen.getByText(/^\+120,000$/)).toBeTruthy();
    expect(screen.getByText(/^-30,000$/)).toBeTruthy();
  });

  it("수급 점수는 소수점을 버리고 정수로 찍는다", () => {
    render(<SupplyDemandCard sd={sd({ korean_flow_score: 62.4 })} />);
    expect(screen.getByText("62 / 100")).toBeTruthy();
  });

  it("순매수·순매도 우위 칩은 buying 만 보고 정한다", () => {
    const { unmount } = render(<SupplyDemandCard sd={sd({ buying: true })} />);
    expect(screen.getByText("순매수 우위")).toBeTruthy();
    unmount();

    // 5일 수치가 양수여도 buying 이 false 면 순매도 우위다. 이 판단은
    // 백엔드가 20일까지 같이 보고 내린다.
    render(<SupplyDemandCard sd={sd({ buying: false, foreign_5d: 120000 })} />);
    expect(screen.getByText("순매도 우위")).toBeTruthy();
  });

  it("외국인 보유비율이 없으면 그 칩 자체가 없다", () => {
    render(<SupplyDemandCard sd={sd({ foreign_hold_ratio: null })} />);
    expect(screen.queryByTitle("외국인 보유비율")).toBeNull();
  });

  it("업종 상대강도는 섹터가 있을 때만 그린다", () => {
    const { unmount } = render(<SupplyDemandCard sd={sd()} />);
    expect(screen.queryByText("업종 상대강도")).toBeNull();
    unmount();

    render(<SupplyDemandCard sd={sd()} sector={sector({ sector_rs: 5.1 })} />);
    expect(screen.getByText("업종 상대강도")).toBeTruthy();
    expect(screen.getByText("+5.1%p")).toBeTruthy();
  });

  it("업종이 뒤처지면 부호를 붙이지 않는다", () => {
    render(<SupplyDemandCard sd={sd()} sector={sector({ sector_rs: -2.4 })} />);
    expect(screen.getByText("-2.4%p")).toBeTruthy();
  });
});
