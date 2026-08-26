"use client";

import {
  fetchAnalysis,
  fetchBuySignals,
  fetchFactorIC,
  fetchPortfolioAnalysis,
  fetchRepresentativeStocks,
  fetchRetroSummary,
  fetchSignalChanges,
  fetchSurgeScan,
  fetchWatchlist,
} from "@/lib/api";
import { useAsyncData, type AsyncData } from "./useAsyncData";
import type {
  AnalysisResponse,
  BuySignalItem,
  ICReport,
  Period,
  PortfolioReport,
  RepresentativeStock,
  RetroSummary,
  SignalChangeSummary,
  SurgeItem,
  WatchlistSummary,
} from "@/lib/types";

/**
 * 화면이 쓰는 조회를 이름으로 부르는 층. 컴포넌트가 엔드포인트 파라미터를
 * 들고 있지 않도록 여기에 모아둔다. 목록 개수나 유니버스 크기 같은 값이
 * 바뀌면 컴포넌트가 아니라 이 파일만 고치면 된다.
 *
 * 쓰기(추가·삭제·계산 요청)는 이벤트가 촉발하므로 여기 없다. 컴포넌트에서
 * `useAsyncAction(lib/api의 함수)`로 직접 쓴다.
 */

/** 새로고침 버튼으로 다시 부른 요청만 서버 캐시를 무시한다. */
const isForced = (attempt: number) => attempt > 0;

export function useAnalysis(ticker: string, period: Period): AsyncData<AnalysisResponse> {
  return useAsyncData(() => fetchAnalysis(ticker, period), [ticker, period], {
    fallbackMessage: "분석 데이터를 불러오지 못했습니다.",
  });
}

export function useBuySignals(enabled: boolean): AsyncData<BuySignalItem[]> {
  return useAsyncData(
    async (attempt) => {
      const res = await fetchBuySignals({
        market: "KR",
        minSignal: "WEAK_BUY",
        limit: 30,
        includeSample: false,
        forceRefresh: isForced(attempt),
      });
      return res.items;
    },
    [],
    { enabled },
  );
}

export function useSurgeScan(enabled: boolean): AsyncData<SurgeItem[]> {
  return useAsyncData(
    async (attempt) => {
      const res = await fetchSurgeScan({
        market: "KR",
        krLimit: 60,
        horizonDays: 10,
        upperPct: 10,
        limit: 30,
        minProbability: 0.2,
        forceRefresh: isForced(attempt),
      });
      return res.items;
    },
    [],
    { enabled },
  );
}

export function useWatchlist(): AsyncData<WatchlistSummary[]> {
  return useAsyncData(() => fetchWatchlist(), []);
}

export function useFactorIC(horizonDays: number, enabled: boolean): AsyncData<ICReport> {
  return useAsyncData(
    (attempt) => fetchFactorIC({ horizonDays, universeSize: 40, forceRefresh: isForced(attempt) }),
    [horizonDays],
    { enabled, fallbackMessage: "IC 계산 실패" },
  );
}

export function useRetroSummary(enabled: boolean): AsyncData<RetroSummary> {
  return useAsyncData(() => fetchRetroSummary(), [], { enabled });
}

/** digest 가 남긴 신호 전환 이력. 패널이 열릴 때만 읽는다. */
export function useSignalChanges(
  enabled: boolean,
  days = 30,
  ticker?: string,
): AsyncData<SignalChangeSummary> {
  return useAsyncData(() => fetchSignalChanges(days, ticker), [days, ticker], {
    enabled,
    fallbackMessage: "신호 이력 조회 실패",
  });
}

/**
 * 이 종목이 최근 30일에 몇 번 뒤집혔나. 없으면 0.
 *
 * 분석 화면은 신호 하나를 보여준다. 그 신호를 얼마나 믿을지는 "이 종목이 원래
 * 자주 뒤집히나"에 달렸는데, 지금까지는 리서치 탭까지 가야 알 수 있었다.
 * 이력이 없어도(디지스트를 안 돌렸어도) 화면이 깨지지 않게 조용히 0을 준다.
 */
export function useTickerFlipCount(ticker: string | undefined): number {
  const { data } = useSignalChanges(Boolean(ticker), 30, ticker);
  if (!data || data.ticker !== ticker) return 0;
  return data.flips[0]?.count ?? 0;
}

/**
 * 검색 자동완성이 거를 종목 목록.
 *
 * `source: "fallback"` 은 백엔드가 들고 있는 고정 목록(KR 100 + US 102)을 그대로
 * 준다. `auto` 는 KRX/미국 지수를 실제로 긁어오느라 수 초가 걸리는데, 자동완성은
 * 최신성보다 즉답이 중요하고 대형주 목록은 하루 이틀 사이에 바뀌지 않는다.
 *
 * `enabled` 로 미루는 이유는 검색을 한 번도 안 쓰는 방문자에게 요청을 만들지
 * 않기 위해서다. 한 번 받으면 훅이 들고 있으므로 다시 부르지 않는다.
 */
export function useTickerUniverse(enabled: boolean): AsyncData<RepresentativeStock[]> {
  return useAsyncData(
    async () => {
      const res = await fetchRepresentativeStocks({ market: "all", source: "fallback" });
      return res.items;
    },
    [],
    { enabled },
  );
}

export function usePortfolio(): AsyncData<PortfolioReport> {
  return useAsyncData(() => fetchPortfolioAnalysis(), [], {
    fallbackMessage: "포트폴리오 분석 실패",
  });
}
