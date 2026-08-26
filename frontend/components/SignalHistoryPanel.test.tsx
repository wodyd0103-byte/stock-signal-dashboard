import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SignalHistoryPanel from "./SignalHistoryPanel";
import type { SignalChangeSummary } from "@/lib/types";

/**
 * 이 패널의 값은 화면이 만들지 않는다 — digest CLI 가 남긴 이력을 읽어 보여줄 뿐이다.
 * 그래서 확인할 것은 계산이 아니라 세 가지다: 접혀 있는 동안 요청하지 않는가,
 * 기록이 없을 때 "고장"이 아니라 "아직 없음"으로 보이는가, 기간을 바꾸면 다시 읽는가.
 *
 * cleanup 을 직접 부르는 이유는 RiskCard.test.tsx 참고.
 */
afterEach(cleanup);

const fetchSignalChanges = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({ fetchSignalChanges }));

function summary(overrides: Partial<SignalChangeSummary> = {}): SignalChangeSummary {
  return {
    days: 30,
    ticker: null,
    total: 3,
    tickers: 2,
    flips: [
      { ticker: "005930", name: "삼성전자", count: 2 },
      { ticker: "000660", name: null, count: 2 },
    ],
    recent: [
      {
        id: 3,
        kind: "signal",
        ticker: "005930",
        name: "삼성전자",
        previous_signal: "BUY",
        current_signal: "HOLD",
        direction: "down",
        buy_score: 2,
        risk_score: 78,
        price: 257000,
        recorded_at: "2026-08-25T08:30:00",
      },
      {
        id: 2,
        kind: "score",
        ticker: "035420",
        name: "NAVER",
        previous_signal: null,
        current_signal: "HOLD",
        direction: "new",
        buy_score: null,
        risk_score: null,
        price: null,
        recorded_at: "2026-08-20T08:30:00",
      },
    ],
    ...overrides,
  };
}

function openPanel() {
  render(<SignalHistoryPanel />);
  fireEvent.click(screen.getByRole("button", { name: /자주 뒤집히나/ }));
}

describe("SignalHistoryPanel", () => {
  it("접혀 있는 동안에는 조회하지 않는다", () => {
    fetchSignalChanges.mockResolvedValue(summary());

    render(<SignalHistoryPanel />);

    expect(fetchSignalChanges).not.toHaveBeenCalled();
  });

  it("열면 30일 기록을 읽어 전환 횟수를 보여준다", async () => {
    fetchSignalChanges.mockResolvedValue(summary());

    openPanel();

    // 패널은 전체 이력을 본다 — 종목 인자 없이 부른다.
    expect(fetchSignalChanges).toHaveBeenCalledWith(30, undefined);
    // 삼성전자는 전환 횟수 목록과 최근 전환 목록 양쪽에 나온다.
    expect((await screen.findAllByText("삼성전자")).length).toBe(2);
    expect(screen.getAllByText("2회")).toHaveLength(2);
    // 이름이 없는 종목은 티커로 표시한다.
    expect(screen.getAllByText("000660").length).toBeGreaterThan(0);
  });

  it("신규 종목은 '신규'로, 점수 이동은 라벨과 함께 읽힌다", async () => {
    fetchSignalChanges.mockResolvedValue(summary());

    openPanel();

    expect(await screen.findByText("신규 HOLD")).toBeTruthy();
    expect(screen.getByText("BUY → HOLD")).toBeTruthy();
    // 등급 전환과 점수 이동이 같은 목록에 섞이므로 무엇이 움직였는지 적는다.
    expect(screen.getByText("매수점수")).toBeTruthy();
  });

  it("기록이 없으면 고장이 아니라 아직 없음으로 안내한다", async () => {
    fetchSignalChanges.mockResolvedValue(summary({ total: 0, tickers: 0, flips: [], recent: [] }));

    openPanel();

    expect(await screen.findByText(/아직 기록된 전환이 없습니다/)).toBeTruthy();
    expect(screen.getByText("python -m tools.digest")).toBeTruthy();
  });

  it("전환은 있으나 두 번 이상 뒤집힌 종목이 없으면 그렇게 말한다", async () => {
    fetchSignalChanges.mockResolvedValue(summary({ flips: [] }));

    openPanel();

    expect(await screen.findByText(/두 번 이상 뒤집힌 종목은 없습니다/)).toBeTruthy();
  });

  it("기간을 바꾸면 그 기간으로 다시 읽는다", async () => {
    fetchSignalChanges.mockResolvedValue(summary());

    openPanel();
    await screen.findAllByText("삼성전자");
    fireEvent.click(screen.getByRole("button", { name: "90일" }));

    expect(fetchSignalChanges).toHaveBeenLastCalledWith(90, undefined);
  });
});
