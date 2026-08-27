/** 보유 종목 분석, 종목 비교, 최적화·리밸런싱. */

export interface HoldingAnalysis {
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  cost: number;
  pnl: number;
  pnl_pct: number;
  weight: number;
  signal: string;
  buy_score: number;
  risk_score: number;
  error?: string | null;
}

export interface HighCorrPair {
  a: string;
  b: string;
  corr: number;
}

export interface PortfolioReport {
  holdings: HoldingAnalysis[];
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  concentration_hhi: number;
  top_weight: number;
  weighted_risk: number;
  signal_counts: Record<string, number>;
  advice: string[];
  high_corr_pairs: HighCorrPair[];
  avg_corr: number;
}

export interface CompareItem {
  ticker: string;
  market?: string;
  current_price?: number;
  change_rate?: number;
  return_20d?: number | null;
  return_60d?: number | null;
  volatility?: number | null;
  signal?: string;
  buy_score?: number;
  risk_score?: number;
  per?: number | null;
  pbr?: number | null;
  error?: string;
}

export interface CompareResponse {
  items: CompareItem[];
  disclaimer?: string;
  updated_at?: string;
  error?: string;
}

export interface OptimizeResult {
  method: "max_sharpe" | "min_variance";
  weights: Record<string, number>;
  exp_return: number;
  exp_vol: number;
  sharpe: number;
  note: string;
  error?: string;
}

export interface RebalanceTrade {
  ticker: string;
  name: string;
  current_weight: number;
  target_weight: number;
  current_price: number;
  delta_shares: number;
  delta_value: number;
  action: "buy" | "sell" | "hold";
  signal: string;
}

export interface RebalancePlan {
  strategy: string;
  total_assets: number;
  investable: number;
  cash: number;
  cash_buffer_pct: number;
  max_weight: number;
  trades: RebalanceTrade[];
  buy_total: number;
  sell_total: number;
  est_commission: number;
  est_tax: number;
  est_cost_total: number;
  residual_cash: number;
  note: string;
  error?: string;
}
