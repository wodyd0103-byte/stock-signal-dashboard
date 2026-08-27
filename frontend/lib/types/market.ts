/**
 * 종목 하나가 아니라 그 종목을 둘러싼 것들 — 수급, 뉴스, 공시, 펀더멘털,
 * 섹터, 시장 심리, 팩터 IC, 학습 신호.
 */

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
