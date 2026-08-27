/**
 * 여러 도메인이 함께 쓰는 조각들.
 *
 * 여기 있는 것은 이 앱 전체가 같은 뜻으로 쓰는 말이다. 특정 화면에서만 쓰이는
 * 타입은 이 파일이 아니라 그 도메인 파일에 둔다.
 */

export type Period = "1mo" | "3mo" | "6mo" | "1y" | "3y";
export type Signal =
  "STRONG BUY" | "BUY" | "WEAK BUY" | "HOLD" | "WEAK SELL" | "SELL" | "STRONG SELL";
export type Market = "KR" | "US";
export type MarketFilter = "all" | Market;
export type MinSignal = "WEAK_BUY" | "BUY" | "STRONG_BUY";
export type UniverseSource = "auto" | "fallback" | "mixed" | "pykrx" | "wikipedia" | string;
export type BuySignalSortBy = "signal" | "buy_score" | "risk_score" | "change_rate";
export type BacktestStrategy =
  | "absolute_score_strategy"
  | "percentile_rank_strategy"
  | "ml_probability_strategy"
  | "regime_adjusted_strategy";

export interface DataSourceMetadata {
  market: Market | string;
  source: "pykrx" | "yfinance" | "FinanceDataReader" | "sample" | "none" | string;
  is_sample: boolean;
  provider_status: "success" | "fallback" | "error" | string;
  provider_message: string;
  provider_error?: string | null;
}

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma120?: number | null;
  rsi?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
  bollinger_upper?: number | null;
  bollinger_lower?: number | null;
}
