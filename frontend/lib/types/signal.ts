/** 지표·신호 점수·리스크. 분석 화면의 신호 카드와 지표 표가 읽는 것들. */

import type { DataSourceMetadata, Signal } from "./common";

export interface IndicatorDetail {
  name: string;
  value: number | string | null;
  interpretation: string;
  influence: string;
  contribution: number;
}

export interface SupportResistance {
  support: number[];
  resistance: number[];
  recent_high: number;
  recent_low: number;
}

export interface SignalScore {
  signal: Signal;
  buy_score: number;
  sell_score: number;
  risk_score: number;
  raw_buy_score: number;
  raw_sell_score: number;
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
  final_buy_score: number;
  final_sell_score: number;
  market_regime?: string | null;
  signal_source: string;
  score_adjustments: string[];
  hold_reasons: string[];
  buy_score_zone: string;
  sell_score_zone: string;
  risk_score_zone: string;
  score_zone: string;
  signal_description: string;
  reasons: string[];
  buy_factors: string[];
  sell_factors: string[];
}

export interface RiskMetric {
  name: string;
  value: number | string | boolean;
  interpretation: string;
  contribution: number;
}

export interface RiskResponse {
  ticker: string;
  period: string;
  risk_score: number;
  risk_level: string;
  metrics: RiskMetric[];
  reasons: string[];
}

export interface SignalResponse extends SignalScore, DataSourceMetadata {
  ticker: string;
  period: string;
}
