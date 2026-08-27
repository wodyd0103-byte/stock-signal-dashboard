/** 종목을 찾는 쪽 — 관심 목록, 대표 종목, 매수 신호 스캔, 급등 탐색. */

import type { DataSourceMetadata, Market, MarketFilter, Signal, UniverseSource } from "./common";

export interface WatchlistSummary {
  id: number;
  ticker: string;
  name?: string | null;
  current_price?: number | null;
  change_rate?: number | null;
  signal?: Signal | null;
  buy_score?: number | null;
  sell_score?: number | null;
  risk_score?: number | null;
  last_analyzed_at?: string | null;
  error?: string | null;
}

export interface RepresentativeStock {
  name: string;
  ticker: string;
  market: Market;
}

export interface RepresentativeStocksResponse {
  market: MarketFilter;
  kr_count: number;
  us_count: number;
  total_count: number;
  source: UniverseSource;
  items: RepresentativeStock[];
  updated_at: string;
}

export interface BuySignalItem extends DataSourceMetadata {
  rank: number;
  name: string;
  ticker: string;
  market: Market;
  current_price: number;
  change_rate: number;
  signal: Signal;
  buy_score: number;
  sell_score: number;
  risk_score: number;
  raw_buy_score: number;
  raw_sell_score: number;
  final_buy_score: number;
  final_sell_score: number;
  buy_score_percentile?: number | null;
  sell_score_percentile?: number | null;
  relative_strength_score?: number | null;
  relative_strength_rank?: number | null;
  liquidity_score?: number | null;
  liquidity_rank?: number | null;
  risk_rank?: number | null;
  regime_score?: number | null;
  ml_up_probability?: number | null;
  ml_signal?: string | null;
  model_confidence?: number | null;
  market_regime?: string | null;
  signal_source: string;
  hold_reasons: string[];
  score_adjustments: string[];
  buy_score_zone: string;
  sell_score_zone: string;
  risk_score_zone: string;
  score_zone: string;
  signal_description: string;
  reasons: string[];
  last_analyzed_at: string;
}

export interface FailedSignalItem {
  name: string;
  ticker: string;
  market: Market;
  error: string;
  provider_error?: string | null;
}

export interface SurgeItem extends DataSourceMetadata {
  rank: number;
  ticker: string;
  name: string;
  market: string;
  current_price: number;
  change_rate: number;
  surge_probability: number;
  base_rate: number;
  lift: number;
  expected_target_pct: number;
  horizon_days: number;
  signal_label: string;
  train_samples: number;
  train_positive: number;
  cv_score: number;
  reasons: string[];
}

export interface SurgeScanResponse {
  updated_at: string;
  horizon_days: number;
  upper_pct: number;
  lower_pct: number;
  market: string;
  items: SurgeItem[];
  failed: { ticker: string; name: string; market: string; error: string }[];
  total_scanned: number;
  total_strong: number;
  disclaimer: string;
}

export interface BuySignalsResponse {
  updated_at: string;
  refresh_seconds: number;
  market: MarketFilter;
  source: UniverseSource;
  market_regime?: string;
  regime_score?: number;
  regime_description?: string;
  kr_checked: number;
  us_checked: number;
  total_checked: number;
  total_success: number;
  total_failed: number;
  total_matched: number;
  strong_buy_count: number;
  buy_count: number;
  weak_buy_count: number;
  items: BuySignalItem[];
  failed_items: FailedSignalItem[];
  disclaimer: string;
}
