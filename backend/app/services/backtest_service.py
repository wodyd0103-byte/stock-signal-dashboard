from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.schemas.backtest import BacktestPoint, BacktestResponse, StrategyBacktestSummary, TradeRecord
from app.services.ml_signal_service import MLSignalService
from app.services.regime_service import RegimeService
from app.services.risk_service import RiskService
from app.services.signal_service import SignalService


SUPPORTED_STRATEGIES = {
    "absolute_score_strategy",
    "percentile_rank_strategy",
    "ml_probability_strategy",
    "regime_adjusted_strategy",
}

# 거래 비용 (KR)
COMMISSION_RATE = 0.00015   # 위탁수수료 (양방)
SELL_TAX_RATE = 0.0018      # 증권거래세 (매도)
SLIPPAGE_RATE = 0.001       # 시장가 슬리피지 (편도)
PRICE_LIMIT = 0.30          # 상하한가 ±30%


def tick_size(price: float) -> float:
    """KRX 호가단위 (2023.1 개편 기준)."""
    if price < 2000: return 1
    if price < 5000: return 5
    if price < 20000: return 10
    if price < 50000: return 50
    if price < 200000: return 100
    if price < 500000: return 500
    return 1000


def round_to_tick(price: float) -> float:
    t = tick_size(price)
    return round(price / t) * t


class BacktestService:
    def __init__(self) -> None:
        self.signal_service = SignalService()
        self.risk_service = RiskService()
        self.regime_service = RegimeService()
        self.ml_signal_service = MLSignalService()

    def run(
        self,
        ticker: str,
        period: str,
        enriched: pd.DataFrame,
        initial_capital: float = 10_000_000,
        *,
        strategy: str = "regime_adjusted_strategy",
    ) -> BacktestResponse:
        if len(enriched) < 45:
            raise ValueError("백테스트를 수행하려면 최소 45거래일 이상의 데이터가 필요합니다.")

        selected_strategy = strategy if strategy in SUPPORTED_STRATEGIES else "regime_adjusted_strategy"
        strategy_runs = {
            name: self._run_single_strategy(enriched, initial_capital, name)
            for name in SUPPORTED_STRATEGIES
        }
        selected = strategy_runs[selected_strategy]
        hold_return = selected["chart"][-1].hold_return if selected["chart"] else 0.0
        summaries = [
            StrategyBacktestSummary(
                strategy=name,
                total_return=run["total_return"],
                max_drawdown=run["max_drawdown"],
                win_rate=run["win_rate"],
                trade_count=run["trade_count"],
                average_trade_return=run["average_trade_return"],
                sharpe_ratio=run["sharpe_ratio"],
            )
            for name, run in sorted(strategy_runs.items())
        ]

        return BacktestResponse(
            ticker=ticker.upper(),
            period=period,
            strategy=selected_strategy,
            initial_capital=initial_capital,
            total_return=selected["total_return"],
            max_drawdown=selected["max_drawdown"],
            sharpe_ratio=selected["sharpe_ratio"],
            win_rate=selected["win_rate"],
            trade_count=selected["trade_count"],
            average_trade_return=selected["average_trade_return"],
            buy_and_hold_return=round(hold_return, 2),
            legacy_strategy_return=strategy_runs["absolute_score_strategy"]["total_return"],
            new_strategy_return=strategy_runs["regime_adjusted_strategy"]["total_return"],
            strategy_results=summaries,
            chart=selected["chart"],
            trades=selected["trades"],
            note="당일 신호를 다음 거래일 시가에 체결(각 시점까지 데이터만 사용). 호가단위·상하한가±30%·슬리피지 0.1%·수수료 0.015%·거래세 0.18% 반영. 실제 체결/유동성과 차이날 수 있습니다.",
        )

    def _run_single_strategy(self, enriched: pd.DataFrame, initial_capital: float, strategy: str) -> dict[str, Any]:
        df = enriched.copy().reset_index(drop=True)
        cash = float(initial_capital)
        shares = 0.0
        entry_price: float | None = None
        entry_date: date | None = None
        trades: list[TradeRecord] = []
        chart: list[BacktestPoint] = []

        start_index = min(120, max(20, len(df) // 8))
        hold_start_price = float(df.iloc[start_index]["open"])
        hold_shares = initial_capital / hold_start_price if hold_start_price else 0.0
        last_signal = "HOLD"

        for index in range(start_index, len(df)):
            row = df.iloc[index]
            if index < len(df) - 1:
                frame_so_far = df.iloc[: index + 1].copy()
                risk_score = self._rolling_risk(frame_so_far)
                signal = self._strategy_signal(frame_so_far, risk_score, strategy)
                prev_close = float(df.iloc[index]["close"])
                next_open = float(df.iloc[index + 1]["open"])
                next_date = df.iloc[index + 1]["date"]
                # 상하한가 캡 (전일 종가 ±30%)
                hi, lo = prev_close * (1 + PRICE_LIMIT), prev_close * (1 - PRICE_LIMIT)
                next_open = max(lo, min(hi, next_open))

                if signal in {"STRONG BUY", "BUY", "WEAK BUY"} and shares == 0 and cash > 0 and next_open > 0:
                    # 매수 체결가 = 시가 + 슬리피지, 호가단위 반올림
                    fill = round_to_tick(next_open * (1 + SLIPPAGE_RATE))
                    invest = cash / (1 + COMMISSION_RATE)   # 수수료 차감 후 투자금
                    shares = invest / fill
                    cash = 0.0
                    entry_price = fill
                    entry_date = next_date
                elif signal in {"STRONG SELL", "SELL", "WEAK SELL"} and shares > 0 and next_open > 0:
                    # 매도 체결가 = 시가 - 슬리피지, 호가단위; 수수료+거래세 차감
                    fill = round_to_tick(next_open * (1 - SLIPPAGE_RATE))
                    gross = shares * fill
                    cash = gross * (1 - COMMISSION_RATE - SELL_TAX_RATE)
                    ep = entry_price or fill
                    # 순수익률 (비용 반영)
                    trade_return = (cash - shares * ep) / (shares * ep) * 100 if ep else 0.0
                    trades.append(
                        TradeRecord(
                            entry_date=entry_date or next_date,
                            exit_date=next_date,
                            entry_price=round(ep, 2),
                            exit_price=round(fill, 2),
                            return_pct=round(trade_return, 2),
                        )
                    )
                    shares = 0.0
                    entry_price = None
                    entry_date = None
                last_signal = signal

            close_price = float(row["close"])
            portfolio_value = cash + shares * close_price
            hold_value = hold_shares * close_price
            chart.append(
                BacktestPoint(
                    date=row["date"],
                    portfolio_value=round(portfolio_value, 2),
                    hold_value=round(hold_value, 2),
                    cumulative_return=round((portfolio_value - initial_capital) / initial_capital * 100, 2),
                    hold_return=round((hold_value - initial_capital) / initial_capital * 100, 2),
                    signal=last_signal,
                )
            )

        if shares > 0 and entry_price is not None:
            final = df.iloc[-1]
            final_price = float(final["close"])
            trades.append(
                TradeRecord(
                    entry_date=entry_date or final["date"],
                    exit_date=None,
                    entry_price=round(entry_price, 2),
                    exit_price=None,
                    return_pct=round((final_price - entry_price) / entry_price * 100, 2),
                )
            )

        values = pd.Series([point.portfolio_value for point in chart])
        total_return = chart[-1].cumulative_return if chart else 0.0
        closed_returns = [trade.return_pct for trade in trades if trade.exit_date is not None and trade.return_pct is not None]
        win_rate = len([value for value in closed_returns if value > 0]) / len(closed_returns) * 100 if closed_returns else 0.0
        average_return = sum(closed_returns) / len(closed_returns) if closed_returns else 0.0

        return {
            "total_return": round(total_return, 2),
            "max_drawdown": round(self.risk_service.max_drawdown(values), 2),
            "sharpe_ratio": self._sharpe(values),
            "win_rate": round(win_rate, 2),
            "trade_count": len(trades),
            "average_trade_return": round(average_return, 2),
            "chart": chart,
            "trades": trades,
        }

    def _strategy_signal(self, frame: pd.DataFrame, risk_score: int, strategy: str) -> str:
        regime = self.regime_service.analyze_from_frame(frame).to_dict() if strategy == "regime_adjusted_strategy" else {"market_regime": "SIDEWAYS", "regime_score": 0, "adjustments": []}
        ml_signal = None
        if strategy == "ml_probability_strategy":
            ml_signal = self.ml_signal_service.predict_up_probability(frame, self._return_pct(frame, 20)).to_dict()

        signal = self.signal_service.score(
            frame,
            risk_score,
            ml_signal=ml_signal,
            regime=regime,
            relative_strength_score=self._return_pct(frame, 20),
            liquidity_score=self._liquidity_score(frame),
            signal_source=strategy,
        )

        if strategy != "percentile_rank_strategy":
            return signal.signal

        return_20d = self._return_pct(frame, 20)
        history = frame["close"].pct_change(20).dropna() * 100
        percentile = float((history <= return_20d).mean() * 100) if len(history) else 50.0
        if percentile >= 90 and risk_score <= 65 and signal.final_buy_score >= 55:
            return "BUY"
        if percentile >= 70 and risk_score <= 75 and signal.final_buy_score >= 50:
            return "WEAK BUY"
        if percentile <= 15 and signal.final_sell_score >= 50:
            return "SELL"
        if percentile <= 30 and signal.final_sell_score >= 45:
            return "WEAK SELL"
        return "HOLD"

    def _rolling_risk(self, frame: pd.DataFrame) -> int:
        returns = frame["close"].pct_change().dropna()
        volatility = float(returns.tail(20).std() * 100) if len(returns) > 2 else 0.0
        mdd = abs(self.risk_service.max_drawdown(frame["close"].tail(60)))
        return min(100, int(volatility * 6 + mdd * 1.2))

    def _return_pct(self, frame: pd.DataFrame, days: int) -> float:
        if len(frame) <= days:
            return 0.0
        base = float(frame.iloc[-days - 1]["close"])
        if base == 0:
            return 0.0
        return round((float(frame.iloc[-1]["close"]) / base - 1) * 100, 2)

    def _liquidity_score(self, frame: pd.DataFrame) -> float:
        value = frame["close"] * frame["volume"]
        latest = float(value.iloc[-1]) if len(value) else 0.0
        average = float(value.tail(20).mean()) if len(value) else latest
        ratio = latest / average if average else 1.0
        return round(max(0, min(100, 45 + ratio * 25)), 2)

    def _sharpe(self, values: pd.Series) -> float | None:
        returns = values.pct_change().dropna()
        if len(returns) < 2 or float(returns.std()) == 0:
            return None
        return round(float((returns.mean() / returns.std()) * np.sqrt(252)), 3)
