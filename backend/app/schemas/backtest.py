from datetime import date

from pydantic import BaseModel

from app.schemas.stock import DataSourceMetadata


class BacktestPoint(BaseModel):
    date: date
    portfolio_value: float
    hold_value: float
    cumulative_return: float
    hold_return: float
    signal: str


class TradeRecord(BaseModel):
    entry_date: date
    exit_date: date | None
    entry_price: float
    exit_price: float | None
    return_pct: float | None


class StrategyBacktestSummary(BaseModel):
    strategy: str
    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    average_trade_return: float
    sharpe_ratio: float | None = None


class BacktestResponse(DataSourceMetadata):
    ticker: str
    period: str
    strategy: str = "regime_adjusted_strategy"
    initial_capital: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float | None = None
    win_rate: float
    trade_count: int
    average_trade_return: float
    buy_and_hold_return: float
    legacy_strategy_return: float | None = None
    new_strategy_return: float | None = None
    strategy_results: list[StrategyBacktestSummary] = []
    chart: list[BacktestPoint]
    trades: list[TradeRecord]
    note: str
