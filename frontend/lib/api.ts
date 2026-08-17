import type {
  AnalysisResponse,
  BacktestResponse,
  BacktestStrategy,
  BuySignalSortBy,
  BuySignalsResponse,
  CompareResponse,
  MarketFilter,
  MinSignal,
  Period,
  ICReport,
  MarketSentiment,
  OptimizeResult,
  PortfolioReport,
  RebalancePlan,
  RepresentativeStocksResponse,
  RetroSummary,
  SurgeScanResponse,
  WatchlistSummary,
} from "./types";

/**
 * 데모 배포는 백엔드 없이 돌아간다. 응답은 `public/api/demo/` 아래에 정적 파일로
 * 놓이고(`scripts/build-demo-api.mjs`), 값이 고정이라는 사실은 DemoBanner가 알린다.
 */
export const IS_DEMO = process.env.NEXT_PUBLIC_DEMO === "1";

/** GitHub Pages 프로젝트 페이지는 하위 경로에 서빙된다. fetch 경로에는 자동으로 안 붙는다. */
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (IS_DEMO ? `${BASE_PATH}/api/demo` : "http://127.0.0.1:8000/api");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    });
  } catch (error) {
    throw new Error(
      `백엔드 서버에 연결할 수 없습니다. FastAPI가 ${API_BASE}에서 실행 중인지 확인하세요.`,
    );
  }

  if (!response.ok) {
    const body = await response.text();
    let message = "API 요청에 실패했습니다.";

    // 정적 호스팅(데모)에서는 없는 경로에 404 HTML 페이지가 돌아온다. 그대로
    // 화면에 뿌리면 마크업이 토스트에 박히므로, 그때는 사람이 읽을 문장을 쓴다.
    if (body.trimStart().startsWith("<")) {
      throw new Error(
        IS_DEMO
          ? "데모에는 이 데이터가 없습니다. 미리 받아둔 응답만 포함돼 있습니다."
          : `요청한 경로를 찾을 수 없습니다 (${response.status}).`,
      );
    }

    if (body) {
      try {
        const parsed = JSON.parse(body) as { detail?: unknown };
        if (typeof parsed.detail === "string") {
          message = parsed.detail;
        } else if (
          parsed.detail &&
          typeof parsed.detail === "object" &&
          "provider_error" in parsed.detail &&
          typeof (parsed.detail as { provider_error?: unknown }).provider_error === "string"
        ) {
          message = (parsed.detail as { provider_error: string }).provider_error;
        } else {
          message = body;
        }
      } catch {
        message = body;
      }
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function fetchAnalysis(ticker: string, period: Period): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(
    `/stocks/${encodeURIComponent(ticker)}/analysis?period=${period}`,
  );
}

export function fetchBacktest(
  ticker: string,
  period: Period,
  initialCapital: number,
  strategy: BacktestStrategy = "regime_adjusted_strategy",
): Promise<BacktestResponse> {
  return request<BacktestResponse>(
    `/stocks/${encodeURIComponent(ticker)}/backtest?period=${period}&initial_capital=${initialCapital}&strategy=${strategy}`,
  );
}

export function fetchRepresentativeStocks(params?: {
  market?: MarketFilter;
  krLimit?: number;
  usLimit?: number;
  source?: "auto" | "fallback";
}): Promise<RepresentativeStocksResponse> {
  const search = new URLSearchParams({
    market: params?.market ?? "all",
    kr_limit: String(params?.krLimit ?? 100),
    us_limit: String(params?.usLimit ?? 100),
    source: params?.source ?? "auto",
  });
  return request<RepresentativeStocksResponse>(
    `/market/representative-stocks?${search.toString()}`,
  );
}

export function fetchBuySignals(params: {
  market: MarketFilter;
  minSignal: MinSignal;
  krLimit?: number;
  usLimit?: number;
  limit?: number;
  includeSample: boolean;
  source?: "auto" | "fallback";
  sortBy?: BuySignalSortBy;
  forceRefresh?: boolean;
}): Promise<BuySignalsResponse> {
  const search = new URLSearchParams({
    market: params.market,
    min_signal: params.minSignal,
    kr_limit: String(params.krLimit ?? 100),
    us_limit: String(params.usLimit ?? 100),
    limit: String(params.limit ?? 20),
    include_sample: String(params.includeSample),
    source: params.source ?? "auto",
    sort_by: params.sortBy ?? "signal",
    force_refresh: String(params.forceRefresh ?? false),
  });
  return request<BuySignalsResponse>(`/market/buy-signals?${search.toString()}`);
}

export function fetchCompare(tickers: string[]): Promise<CompareResponse> {
  const search = new URLSearchParams({ tickers: tickers.join(",") });
  return request<CompareResponse>(`/market/compare?${search.toString()}`);
}

export function fetchWatchlist(): Promise<WatchlistSummary[]> {
  return request<WatchlistSummary[]>("/watchlist");
}

export function addWatchlist(
  ticker: string,
  name?: string,
): Promise<{ id: number; ticker: string; name?: string | null }> {
  return request("/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker, name }),
  });
}

export function deleteWatchlist(ticker: string): Promise<void> {
  return request<void>(`/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
}

export function fetchPortfolioAnalysis(): Promise<PortfolioReport> {
  return request<PortfolioReport>("/portfolio/analysis");
}

export function fetchRebalance(params: {
  cash?: number;
  strategy?: "equal" | "signal" | "risk_parity";
  maxWeight?: number;
  cashBuffer?: number;
  weights?: string;
}): Promise<RebalancePlan> {
  const search = new URLSearchParams({
    cash: String(params.cash ?? 0),
    strategy: params.strategy ?? "signal",
    max_weight: String(params.maxWeight ?? 35),
    cash_buffer: String(params.cashBuffer ?? 0),
  });
  if (params.weights) search.set("weights", params.weights);
  return request<RebalancePlan>(`/portfolio/rebalance?${search.toString()}`);
}

export function fetchOptimize(params?: {
  method?: "max_sharpe" | "min_variance";
  maxWeight?: number;
}): Promise<OptimizeResult> {
  const search = new URLSearchParams({
    method: params?.method ?? "max_sharpe",
    max_weight: String(params?.maxWeight ?? 40),
  });
  return request<OptimizeResult>(`/portfolio/optimize?${search.toString()}`);
}

export function addHolding(payload: {
  ticker: string;
  name?: string;
  quantity: number;
  avg_price: number;
}) {
  return request("/portfolio/holdings", { method: "POST", body: JSON.stringify(payload) });
}

export function deleteHolding(ticker: string): Promise<void> {
  return request<void>(`/portfolio/holdings/${encodeURIComponent(ticker)}`, { method: "DELETE" });
}

export function fetchRetroSummary(): Promise<RetroSummary> {
  return request<RetroSummary>("/retrospective/summary");
}

export function evaluateRetro(): Promise<RetroSummary & { evaluated: number }> {
  return request("/retrospective/evaluate", { method: "POST" });
}

export function fetchFactorIC(params?: {
  horizonDays?: number;
  universeSize?: number;
  forceRefresh?: boolean;
}): Promise<ICReport> {
  const search = new URLSearchParams({
    horizon_days: String(params?.horizonDays ?? 5),
    universe_size: String(params?.universeSize ?? 40),
    force_refresh: String(params?.forceRefresh ?? false),
  });
  return request<ICReport>(`/ic/factors?${search.toString()}`);
}

export function fetchMarketSentiment(forceRefresh = false): Promise<MarketSentiment> {
  return request<MarketSentiment>(`/market/sentiment?force_refresh=${forceRefresh}`);
}

export function fetchSurgeScan(params: {
  market?: "all" | "KR" | "US";
  krLimit?: number;
  usLimit?: number;
  horizonDays?: number;
  upperPct?: number;
  lowerPct?: number;
  limit?: number;
  minProbability?: number;
  forceRefresh?: boolean;
}): Promise<SurgeScanResponse> {
  const search = new URLSearchParams({
    market: params.market ?? "KR",
    kr_limit: String(params.krLimit ?? 60),
    us_limit: String(params.usLimit ?? 0),
    horizon_days: String(params.horizonDays ?? 10),
    upper_pct: String(params.upperPct ?? 10),
    lower_pct: String(params.lowerPct ?? 5),
    limit: String(params.limit ?? 30),
    min_probability: String(params.minProbability ?? 0),
    force_refresh: String(params.forceRefresh ?? false),
  });
  return request<SurgeScanResponse>(`/surge/scan?${search.toString()}`);
}

/**
 * CSV 다운로드용 URL 생성.
 * fetch 대신 window.location 또는 <a download>로 직접 호출 → 브라우저가 파일 저장.
 */
export function buildBuySignalsCsvUrl(params: {
  market: MarketFilter;
  minSignal: MinSignal;
  krLimit?: number;
  usLimit?: number;
  limit?: number;
  includeSample?: boolean;
  source?: "auto" | "fallback";
  sortBy?: BuySignalSortBy;
  forceRefresh?: boolean;
}): string {
  const search = new URLSearchParams({
    market: params.market,
    min_signal: params.minSignal,
    kr_limit: String(params.krLimit ?? 100),
    us_limit: String(params.usLimit ?? 100),
    limit: String(params.limit ?? 50),
    include_sample: String(params.includeSample ?? false),
    source: params.source ?? "auto",
    sort_by: params.sortBy ?? "signal",
    force_refresh: String(params.forceRefresh ?? false),
  });
  return `${API_BASE}/export/buy-signals.csv?${search.toString()}`;
}

export function buildWatchlistCsvUrl(): string {
  return `${API_BASE}/export/watchlist.csv`;
}

export function buildStockCsvUrl(ticker: string, period: Period = "1y"): string {
  return `${API_BASE}/export/stock/${encodeURIComponent(ticker)}.csv?period=${period}`;
}

export const periods: Array<{ value: Period; label: string }> = [
  { value: "1mo", label: "1개월" },
  { value: "3mo", label: "3개월" },
  { value: "6mo", label: "6개월" },
  { value: "1y", label: "1년" },
  { value: "3y", label: "3년" },
];
