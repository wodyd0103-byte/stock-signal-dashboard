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

export interface SignalResponse extends SignalScore, DataSourceMetadata {
  ticker: string;
  period: string;
}

export interface AnalysisResponse extends DataSourceMetadata {
  ticker: string;
  period: string;
  current_price: number;
  previous_close: number;
  change: number;
  change_rate: number;
  volume: number;
  signal: SignalScore;
  indicators: IndicatorDetail[];
  risk: RiskResponse;
  predictions: HorizonPrediction[];
  long_term_predictions?: HorizonPrediction[];
  optimal_exit?: OptimalExit | null;
  price_target?: PriceTarget | null;
  market_sentiment?: MarketSentiment | null;
  supply_demand?: SupplyDemand | null;
  news_sentiment?: NewsSentiment | null;
  sector?: SectorStrength | null;
  disclosure?: DisclosureInfo | null;
  learned_signal?: LearnedSignal | null;
  fundamental?: Fundamental | null;
  price_history: PricePoint[];
  levels: SupportResistance;
  disclaimer: string;
  last_updated: string;
}

export interface BacktestPoint {
  date: string;
  portfolio_value: number;
  hold_value: number;
  cumulative_return: number;
  hold_return: number;
  signal: string;
}

export interface TradeRecord {
  entry_date: string;
  exit_date: string | null;
  entry_price: number;
  exit_price: number | null;
  return_pct: number | null;
}

export interface BacktestResponse extends DataSourceMetadata {
  ticker: string;
  period: string;
  strategy: BacktestStrategy | string;
  initial_capital: number;
  total_return: number;
  max_drawdown: number;
  sharpe_ratio?: number | null;
  win_rate: number;
  trade_count: number;
  average_trade_return: number;
  buy_and_hold_return: number;
  legacy_strategy_return?: number | null;
  new_strategy_return?: number | null;
  strategy_results: StrategyBacktestSummary[];
  chart: BacktestPoint[];
  trades: TradeRecord[];
  note: string;
}

export interface StrategyBacktestSummary {
  strategy: string;
  total_return: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  average_trade_return: number;
  sharpe_ratio?: number | null;
}

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

export interface RetroRecord {
  id: number;
  ticker: string;
  name?: string | null;
  market?: string | null;
  signal: string;
  buy_score: number;
  risk_score: number;
  price_at_rec: number;
  recommended_at: string;
  price_after?: number | null;
  return_pct?: number | null;
  horizon_days: number;
  hit?: number | null;
  status: string;
  evaluated_at?: string | null;
}

export interface RetroBySignal {
  signal: string;
  count: number;
  hit_rate: number;
  avg_return: number;
}

export interface RetroSummary {
  total: number;
  evaluated: number;
  open: number;
  hit_rate: number | null;
  avg_return: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  by_signal: RetroBySignal[];
  recent: RetroRecord[];
}

export interface Fundamental {
  ticker: string;
  per: number | null;
  pbr: number | null;
  eps: number | null;
  bps: number | null;
  dividend_yield: number | null;
  roe_est: number | null;
  pos_52w: number | null;
  score: number;
  summary: string;
}

export interface LearnedContribution {
  factor: string;
  label: string;
  ic: number;
  z: number;
  contrib: number;
}

export interface LearnedSignal {
  score: number;
  label: string;
  used_factors: number;
  contributions: LearnedContribution[];
  note: string;
}

export interface FactorIC {
  factor: string;
  label: string;
  ic: number;
  icir: number;
  hit_rate: number;
  n_periods: number;
  verdict: string;
}

export interface ICReport {
  horizon_days: number;
  universe_size: number;
  updated_at: string;
  note: string;
  factors: FactorIC[];
}

export interface SentimentComponent {
  name: string;
  raw_value: number;
  score: number;
  interpretation: string;
}

export interface MarketSentiment {
  score: number;
  label: string;
  risk_on: boolean;
  components: SentimentComponent[];
  updated_at: string;
}

export interface SupplyDemand {
  ticker: string;
  foreign_5d: number;
  foreign_20d: number;
  inst_5d: number;
  inst_20d: number;
  korean_flow_score: number;
  buying: boolean;
  summary: string;
  foreign_hold_ratio?: number | null;
}

export interface DisclosureItem {
  title: string;
  datetime: string;
  author: string;
  category: string;
  important: boolean;
  sentiment: number;
}

export interface DisclosureInfo {
  ticker: string;
  important_count: number;
  has_dilution: boolean;
  items: DisclosureItem[];
}

export interface SectorStrength {
  ticker: string;
  stock_return_20d: number;
  peer_median_20d: number;
  sector_rs: number;
  percentile: number;
  score: number;
  peer_count: number;
  summary: string;
}

export interface NewsHeadline {
  title: string;
  score: number;
}

export interface NewsSentiment {
  ticker: string;
  sentiment_score: number;
  label: string;
  positive_count: number;
  negative_count: number;
  total: number;
  headlines: NewsHeadline[];
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
