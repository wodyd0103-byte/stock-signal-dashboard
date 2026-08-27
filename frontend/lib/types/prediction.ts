/** 단기 예측, 장기 시계, 목표가·매도 시점. */

import type { DataSourceMetadata } from "./common";

export interface ModelPrediction {
  model: string;
  predicted_price: number;
  test_score: number;
}

export interface HorizonPrediction {
  horizon_days: number;
  predicted_price: number;
  expected_return_pct: number;
  model_predictions: ModelPrediction[];
  confidence_score: number;
}

export interface OptimalExit {
  horizon_days: number;
  horizon_label: string;
  target_price: number;
  expected_return_pct: number;
  confidence_score: number;
  risk_adjusted_score: number;
  rationale: string;
}

export interface PriceTarget {
  horizon_days: number;
  conservative_price: number;
  base_price: number;
  optimistic_price: number;
  current_price: number;
  expected_return_pct: number;
  confidence_score: number;
  rationale: string;
}

export interface PredictionResponse extends DataSourceMetadata {
  ticker: string;
  period: string;
  current_price: number;
  predictions: HorizonPrediction[];
  long_term_predictions?: HorizonPrediction[];
  optimal_exit?: OptimalExit | null;
  price_target?: PriceTarget | null;
  feature_columns: string[];
  note: string;
}
