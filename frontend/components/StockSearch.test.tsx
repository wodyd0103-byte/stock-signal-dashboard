import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import StockSearch from "./StockSearch";
import type { RepresentativeStock } from "@/lib/types";

/**
 * 자동완성이 붙으면서 이 폼에는 지켜야 할 계약이 두 개가 됐다.
 *
 * 1. 후보를 고르면 그 종목으로 바로 조회한다.
 * 2. **후보를 고르지 않았으면 친 그대로 보낸다.** 유니버스는 대형주 200종목뿐이고
 *    백엔드는 그 밖의 종목도 조회할 수 있다. 첫 후보를 자동으로 잡아버리면
 *    "AAP"를 치고 Enter 친 사람이 AAPL을 받게 되는데, 이건 자동완성이 붙기 전
 *    이 폼이 하던 일을 빼앗는 것이다.
 *
 * 목록 조회는 훅 뒤에 있으므로 lib/api를 목킹한다. 매칭 규칙 자체는
 * lib/tickerSearch.test.ts가 화면 없이 본다.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

const UNIVERSE: RepresentativeStock[] = [
  { name: "삼성전자", ticker: "005930", market: "KR" },
  { name: "삼성바이오로직스", ticker: "207940", market: "KR" },
  { name: "삼성SDI", ticker: "006400", market: "KR" },
  { name: "Apple", ticker: "AAPL", market: "US" },
];

const fetchRepresentativeStocks = vi.fn(async () => ({
  market: "all" as const,
  kr_count: 3,
  us_count: 1,
  total_count: UNIVERSE.length,
  source: "fallback",
  items: UNIVERSE,
  updated_at: "2026-08-18T00:00:00",
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  // 화살표로 감싸는 이유: vi.mock 은 호이스팅돼서 팩토리가 위 const 보다 먼저
  // 평가된다. 직접 참조하면 초기화 전 접근으로 터진다.
  return { ...actual, fetchRepresentativeStocks: () => fetchRepresentativeStocks() };
});

/** 입력에 포커스를 주고 목록이 로드될 때까지 기다린다. */
async function focusAndType(value: string) {
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  await waitFor(() => expect(fetchRepresentativeStocks).toHaveBeenCalled());
  fireEvent.change(input, { target: { value } });
  return input;
}

function optionTexts() {
  return screen.queryAllByRole("option").map((el) => el.textContent);
}

describe("StockSearch", () => {
  it("포커스 전에는 종목 목록을 부르지 않는다", () => {
    render(<StockSearch onSearch={vi.fn()} />);
    expect(fetchRepresentativeStocks).not.toHaveBeenCalled();
  });

  it("한글 이름 일부로 후보를 보여준다", async () => {
    render(<StockSearch onSearch={vi.fn()} />);
    await focusAndType("삼성");

    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));
    expect(optionTexts()[0]).toContain("삼성전자");
    expect(optionTexts()[0]).toContain("005930");
  });

  it("맞는 후보가 없으면 목록을 열지 않는다", async () => {
    render(<StockSearch onSearch={vi.fn()} />);
    await focusAndType("없는회사");

    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("combobox").getAttribute("aria-expanded")).toBe("false");
  });

  it("후보를 클릭하면 그 종목으로 조회한다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    fireEvent.click(screen.getAllByRole("option")[1]);

    expect(onSearch).toHaveBeenCalledWith("207940", "1y");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("화살표로 내려가 Enter 치면 그 후보로 조회한다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("207940", "1y");
  });

  it("아무것도 안 고르고 Enter 치면 친 그대로 보낸다", async () => {
    // 자동완성이 입력을 가로채면 안 되는 자리. 유니버스에 없는 종목도 조회된다.
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("삼성", "1y");
  });

  it("유니버스에 없는 종목도 그대로 조회한다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("tsla");

    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("TSLA", "1y");
  });

  it("빈 입력은 조회하지 않는다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("   ");

    fireEvent.submit(input.closest("form")!);

    expect(onSearch).not.toHaveBeenCalled();
  });

  it("위 화살표는 마지막 후보로 감는다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    // 아무것도 안 고른 상태(-1)에서 위로 = 마지막.
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("006400", "1y");
  });

  it("아래 화살표는 마지막에서 처음으로 감는다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    for (let i = 0; i < 4; i += 1) fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("005930", "1y");
  });

  it("Escape는 목록만 닫고 입력은 남긴다", async () => {
    render(<StockSearch onSearch={vi.fn()} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.queryByRole("listbox")).toBeNull();
    expect((input as HTMLInputElement).value).toBe("삼성");
  });

  it("입력을 고치면 강조가 처음으로 돌아간다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    fireEvent.keyDown(input, { key: "ArrowDown" }); // 삼성전자 강조
    fireEvent.change(input, { target: { value: "삼성바이오" } });

    // 강조가 남아 있으면 Enter가 남은 위치의 후보를 보낸다. 초기화됐으면 친 그대로.
    fireEvent.submit(input.closest("form")!);
    expect(onSearch).toHaveBeenCalledWith("삼성바이오", "1y");
  });

  it("고른 후보가 aria-activedescendant 로 드러난다", async () => {
    render(<StockSearch onSearch={vi.fn()} />);
    const input = await focusAndType("삼성");
    await waitFor(() => expect(screen.queryAllByRole("option")).toHaveLength(3));

    expect(input.getAttribute("aria-activedescendant")).toBeNull();

    fireEvent.keyDown(input, { key: "ArrowDown" });

    const active = screen.getAllByRole("option")[0];
    expect(input.getAttribute("aria-activedescendant")).toBe(active.id);
    expect(active.getAttribute("aria-selected")).toBe("true");
  });

  it("기간 버튼으로 고른 기간이 조회에 함께 간다", async () => {
    const onSearch = vi.fn();
    render(<StockSearch onSearch={onSearch} />);
    const input = await focusAndType("tsla");

    fireEvent.click(screen.getByText("3개월"));
    fireEvent.submit(input.closest("form")!);

    expect(onSearch).toHaveBeenCalledWith("TSLA", "3mo");
  });

  it("부모가 종목을 바꾸면 입력도 따라간다", () => {
    const { rerender } = render(<StockSearch defaultTicker="AAPL" onSearch={vi.fn()} />);
    expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("AAPL");

    rerender(<StockSearch defaultTicker="005930" onSearch={vi.fn()} />);
    expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("005930");
  });
});
