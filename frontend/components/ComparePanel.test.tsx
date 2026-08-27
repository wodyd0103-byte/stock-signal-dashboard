import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ComparePanel from "./ComparePanel";
import type { CompareItem, CompareResponse } from "@/lib/types";

/**
 * 이 패널이 화면에서 하는 판단은 두 가지다.
 *
 * 1. **무엇을 보낼지** — 2개 미만이면 요청하지 않고, 4개를 넘으면 앞의 넷만 보낸다.
 *    백엔드가 거절하기 전에 여기서 걸러야 사용자가 이유를 바로 본다.
 * 2. **어느 칸을 강조할지** — "초록 강조 = 항목별 우위"라고 화면에 적혀 있다.
 *    수익·점수는 큰 쪽이, 변동성·리스크는 작은 쪽이 우위다. 부호를 한 번만
 *    뒤집어 쓰기 때문에 방향이 반대로 박혀도 표는 멀쩡해 보인다.
 *
 * 요청은 lib/api 뒤에 있으므로 목킹한다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

const fetchCompare = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({ fetchCompare }));

function item(ticker: string, overrides: Partial<CompareItem> = {}): CompareItem {
  return {
    ticker,
    current_price: 100000,
    change_rate: 1.2,
    return_20d: 3,
    return_60d: 5,
    volatility: 20,
    signal: "HOLD",
    buy_score: 50,
    risk_score: 40,
    per: 12.34,
    pbr: 1.234,
    ...overrides,
  };
}

function respond(items: CompareItem[], extra: Partial<CompareResponse> = {}) {
  fetchCompare.mockResolvedValue({ items, ...extra } satisfies CompareResponse);
}

/** 패널을 펼치고, 입력을 주고, 비교를 누른다. */
async function compare(input: string, items: CompareItem[], extra: Partial<CompareResponse> = {}) {
  respond(items, extra);
  render(<ComparePanel currentTicker="005930" />);
  fireEvent.click(screen.getByText("2~4종목 나란히 보기"));
  fireEvent.change(screen.getByLabelText("비교할 종목 (쉼표로 구분)"), {
    target: { value: input },
  });
  fireEvent.click(screen.getByRole("button", { name: "비교" }));
  await waitFor(() => expect(screen.queryByRole("table")).not.toBeNull());
}

/** label 행에서 초록 강조가 붙은 칸의 종목. 없으면 null. */
function highlighted(label: string): string | null {
  const row = screen.getByText(label).closest("tr");
  if (!row) throw new Error(`${label} 행이 없다`);
  const cells = Array.from(row.querySelectorAll("td"));
  const marked = cells.findIndex((td) => td.className.includes("bg-up/10"));
  if (marked < 0) return null;
  // 첫 칸은 지표 이름이므로 헤더의 같은 위치는 marked 번째 종목 버튼이다.
  const headers = within(screen.getByRole("table")).getAllByRole("button");
  return headers[marked - 1]?.textContent ?? null;
}

describe("ComparePanel", () => {
  it("접혀 있는 동안에는 입력도 요청도 없다", () => {
    render(<ComparePanel currentTicker="005930" />);
    expect(screen.queryByLabelText("비교할 종목 (쉼표로 구분)")).toBeNull();
    expect(fetchCompare).not.toHaveBeenCalled();
  });

  it("펼치면 지금 보는 종목이 입력에 들어가 있다", () => {
    render(<ComparePanel currentTicker="005930" />);
    fireEvent.click(screen.getByText("2~4종목 나란히 보기"));
    const input = screen.getByLabelText("비교할 종목 (쉼표로 구분)") as HTMLInputElement;
    expect(input.value).toBe("005930");
  });

  it("종목이 하나뿐이면 요청하지 않고 이유를 말한다", () => {
    render(<ComparePanel currentTicker="005930" />);
    fireEvent.click(screen.getByText("2~4종목 나란히 보기"));
    fireEvent.click(screen.getByRole("button", { name: "비교" }));

    expect(fetchCompare).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("2~4개");
  });

  it("다섯 개를 넣으면 앞의 넷만 보낸다", async () => {
    await compare("005930, 000660, 035420, 051910, 207940", [
      item("005930"),
      item("000660"),
      item("035420"),
      item("051910"),
    ]);
    expect(fetchCompare).toHaveBeenCalledWith(["005930", "000660", "035420", "051910"]);
  });

  it("수익은 큰 쪽을 강조한다", async () => {
    await compare("005930, 000660", [
      item("005930", { return_20d: 3 }),
      item("000660", { return_20d: 9 }),
    ]);
    expect(highlighted("20일 수익")).toBe("000660");
  });

  it("변동성과 리스크는 작은 쪽을 강조한다", async () => {
    await compare("005930, 000660", [
      item("005930", { volatility: 18, risk_score: 30 }),
      item("000660", { volatility: 44, risk_score: 71 }),
    ]);
    expect(highlighted("변동성(연)")).toBe("005930");
    expect(highlighted("리스크")).toBe("005930");
  });

  it("값이 같으면 아무 쪽도 강조하지 않는다", async () => {
    // 둘이 같으면 우위가 없다. 한쪽에 초록을 칠하면 화면 아래 "초록 강조 =
    // 항목별 우위"라는 설명이 거짓말이 된다.
    await compare("005930, 000660", [
      item("005930", { return_20d: 7 }),
      item("000660", { return_20d: 7 }),
    ]);
    expect(highlighted("20일 수익")).toBeNull();
  });

  it("값이 전부 비어 있으면 강조하지 않는다", async () => {
    await compare("005930, 000660", [
      item("005930", { return_60d: null }),
      item("000660", { return_60d: null }),
    ]);
    expect(highlighted("60일 수익")).toBeNull();
  });

  it("실패한 종목은 표에서 빼고 아래에 이유를 적는다", async () => {
    await compare("005930, 000660, 999999", [
      item("005930"),
      item("000660"),
      { ticker: "999999", error: "종목 없음" },
    ]);
    const headers = within(screen.getByRole("table")).getAllByRole("button");
    expect(headers.map((h) => h.textContent)).toEqual(["005930", "000660"]);
    expect(screen.getByText(/999999\(종목 없음\)/)).toBeTruthy();
  });

  it("성공한 종목이 하나뿐이면 표를 그리지 않는다", async () => {
    respond([item("005930"), { ticker: "000660", error: "조회 실패" }]);
    render(<ComparePanel currentTicker="005930" />);
    fireEvent.click(screen.getByText("2~4종목 나란히 보기"));
    fireEvent.change(screen.getByLabelText("비교할 종목 (쉼표로 구분)"), {
      target: { value: "005930, 000660" },
    });
    fireEvent.click(screen.getByRole("button", { name: "비교" }));

    await waitFor(() => expect(fetchCompare).toHaveBeenCalled());
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("200으로 오면서 본문에 담겨 온 오류도 보여준다", async () => {
    respond([item("005930"), item("000660")], { error: "일부 종목을 읽지 못했습니다" });
    render(<ComparePanel currentTicker="005930" />);
    fireEvent.click(screen.getByText("2~4종목 나란히 보기"));
    fireEvent.change(screen.getByLabelText("비교할 종목 (쉼표로 구분)"), {
      target: { value: "005930, 000660" },
    });
    fireEvent.click(screen.getByRole("button", { name: "비교" }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("일부 종목을 읽지 못했습니다"),
    );
  });

  it("없는 값은 '-'로 두고 0으로 채우지 않는다", async () => {
    await compare("005930, 000660", [
      item("005930", { per: null, pbr: null, buy_score: undefined }),
      item("000660"),
    ]);
    const perRow = screen.getByText("PER").closest("tr");
    expect(within(perRow as HTMLElement).getAllByText("-").length).toBe(1);
  });
});
