"use client";

import {
  fetchAnalysis,
  fetchBuySignals,
  fetchFactorIC,
  fetchPortfolioAnalysis,
  fetchRetroSummary,
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
  RetroSummary,
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

export function usePortfolio(): AsyncData<PortfolioReport> {
  return useAsyncData(() => fetchPortfolioAnalysis(), [], {
    fallbackMessage: "포트폴리오 분석 실패",
  });
}
