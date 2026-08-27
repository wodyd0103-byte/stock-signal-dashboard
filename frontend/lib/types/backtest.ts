/** 백테스트 결과와 전략별 요약. */

import type { BacktestStrategy, DataSourceMetadata } from "./common";

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
