from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas.analysis import SignalScore
from app.schemas.prediction import PredictionResponse


class SignalService:
    def score(
        self,
        enriched: pd.DataFrame,
        risk_score: int,
        prediction: PredictionResponse | None = None,
        *,
        ml_signal: dict[str, Any] | None = None,
        regime: dict[str, Any] | None = None,
        korean_market: dict[str, Any] | None = None,
        relative_strength_score: float | None = None,
        liquidity_score: float | None = None,
        market_sentiment: dict[str, Any] | None = None,
        news_sentiment: dict[str, Any] | None = None,
        sector: dict[str, Any] | None = None,
        fundamental: dict[str, Any] | None = None,
        signal_source: str = "absolute_score",
    ) -> SignalScore:
        if enriched.empty:
            raise ValueError("신호를 계산할 가격 데이터가 없습니다.")

        raw_buy_score, raw_sell_score, buy_factors, sell_factors = self._raw_scores(enriched)
        ml_probability = self._ml_probability(ml_signal)
        regime_name = str((regime or {}).get("market_regime") or "SIDEWAYS")
        regime_score = float((regime or {}).get("regime_score") or 0)
        adjustments: list[str] = []

        final_buy_score = float(raw_buy_score)
        final_sell_score = float(raw_sell_score)
        adjusted_risk_score = float(risk_score)

        if ml_probability is not None:
            if ml_probability >= 0.65:
                final_buy_score += 10
                adjustments.append("ML 상승확률이 65% 이상이라 최종 매수 점수를 보강했습니다.")
            elif ml_probability >= 0.60:
                final_buy_score += 6
                adjustments.append("ML 상승확률이 60% 이상이라 매수 점수를 일부 보강했습니다.")
            elif ml_probability <= 0.35:
                final_sell_score += 8
                adjustments.append("ML 상승확률이 낮아 매도 점수를 보강했습니다.")

        final_buy_score, final_sell_score, adjusted_risk_score = self._apply_regime_adjustment(
            regime_name,
            final_buy_score,
            final_sell_score,
            adjusted_risk_score,
            adjustments,
        )

        if liquidity_score is not None:
            if liquidity_score >= 70:
                final_buy_score += 4
                adjustments.append("유동성 점수가 높아 후보 신뢰도를 일부 보강했습니다.")
            elif liquidity_score < 35:
                final_buy_score -= 6
                adjustments.append("유동성이 낮아 매수 점수를 낮췄습니다.")

        if relative_strength_score is not None:
            if relative_strength_score >= 5:
                final_buy_score += 6
                adjustments.append("20일 상대강도가 우수해 최종 매수 점수를 보강했습니다.")
            elif relative_strength_score <= -5:
                final_sell_score += 6
                adjustments.append("20일 상대강도가 약해 최종 매도 점수를 보강했습니다.")

        # 시장 공포·탐욕 지수 (매크로 심리 오버레이)
        if market_sentiment:
            senti = float(market_sentiment.get("score") or 50)
            label = market_sentiment.get("label") or ""
            if senti <= 24:
                final_buy_score -= 8
                adjusted_risk_score += 8
                adjustments.append(f"시장 심리가 '{label}'({senti:.0f})로 위험회피 국면이라 매수를 보수적으로 낮췄습니다.")
            elif senti <= 44:
                final_buy_score -= 4
                adjusted_risk_score += 4
                adjustments.append(f"시장 심리가 '{label}'({senti:.0f})로 다소 위축돼 매수 점수를 일부 낮췄습니다.")
            elif senti >= 75:
                # 극도 탐욕 = 과열. 추격매수 경계
                adjusted_risk_score += 5
                adjustments.append(f"시장 심리가 '{label}'({senti:.0f})로 과열 구간이라 리스크를 일부 높였습니다.")
            elif senti >= 56:
                final_buy_score += 4
                adjustments.append(f"시장 심리가 '{label}'({senti:.0f})로 위험선호 국면이라 매수 점수를 일부 보강했습니다.")

        # 종목 뉴스 감성 (제목 사전 기반)
        if news_sentiment:
            ns = float(news_sentiment.get("sentiment_score") or 50)
            nlabel = news_sentiment.get("label") or ""
            if ns >= 65:
                final_buy_score += 5
                adjustments.append(f"최근 뉴스 감성이 '{nlabel}'({ns:.0f})으로 우호적이라 매수 점수를 보강했습니다.")
            elif ns <= 35:
                final_sell_score += 5
                adjusted_risk_score += 4
                adjustments.append(f"최근 뉴스 감성이 '{nlabel}'({ns:.0f})으로 부정적이라 매도/리스크를 보강했습니다.")

        # 펀더멘털 (저평가·고배당·고ROE)
        if fundamental:
            fs = float(fundamental.get("score") or 50)
            if fs >= 65:
                final_buy_score += 5
                adjustments.append(f"펀더멘털 우호({fundamental.get('summary', '')[:40]})로 매수 점수를 보강했습니다.")
            elif fs <= 35:
                final_buy_score -= 4
                adjustments.append("밸류에이션 부담(고PER/고PBR)으로 매수 점수를 낮췄습니다.")

        # 업종 상대강도 (섹터 내 위치)
        if sector:
            sec_score = float(sector.get("score") or 50)
            rs = float(sector.get("sector_rs") or 0)
            if sec_score >= 70 and rs > 0:
                final_buy_score += 5
                adjustments.append(f"동종업종 대비 상대강도 우수(상위 {100 - sec_score:.0f}%)해 매수 점수를 보강했습니다.")
            elif sec_score <= 30 and rs < 0:
                final_buy_score -= 4
                adjustments.append(f"동종업종 대비 약세(하위 {sec_score:.0f}%)라 매수 점수를 낮췄습니다.")

        if korean_market:
            flow_score = korean_market.get("korean_flow_score")
            if flow_score:
                final_buy_score += min(12, float(flow_score))
                adjustments.append("국내 수급 점수를 최종 매수 점수에 반영했습니다.")
            final_buy_score += float(korean_market.get("liquidity_score_adjustment") or 0)
            adjusted_risk_score += float(korean_market.get("risk_score_adjustment") or 0)
            if korean_market.get("exclude_buy"):
                final_buy_score = min(final_buy_score, 45)
                adjustments.append("시장경보 또는 거래제한 리스크로 매수 후보에서 제외했습니다.")

        # 소프트캡: 85점 초과분 압축 → 모든 보정 단순 덧셈 시 100점 천장에 몰려
        # 변별력 잃는 문제 방지. 순서(ordering)는 보존.
        final_buy = self._clamp(self._soft_cap(final_buy_score))
        final_sell = self._clamp(self._soft_cap(final_sell_score))
        adjusted_risk = self._clamp(adjusted_risk_score)
        signal = self._detail_signal(final_buy, final_sell, adjusted_risk, ml_probability)
        hold_reasons = self._hold_reasons(signal, final_buy, final_sell, adjusted_risk, ml_probability, regime_name, liquidity_score)
        description = self._signal_description(signal, final_buy, final_sell, adjusted_risk, ml_probability, signal_source)
        reasons = self._reasons(signal, final_buy, final_sell, adjusted_risk, buy_factors, sell_factors, description, hold_reasons)

        return SignalScore(
            signal=signal,
            buy_score=final_buy,
            sell_score=final_sell,
            risk_score=adjusted_risk,
            raw_buy_score=raw_buy_score,
            raw_sell_score=raw_sell_score,
            relative_strength_score=round(float(relative_strength_score), 2) if relative_strength_score is not None else None,
            liquidity_score=round(float(liquidity_score), 2) if liquidity_score is not None else None,
            regime_score=round(regime_score, 2),
            ml_up_probability=ml_probability,
            ml_signal=(ml_signal or {}).get("ml_signal"),
            model_confidence=(ml_signal or {}).get("model_confidence"),
            final_buy_score=final_buy,
            final_sell_score=final_sell,
            market_regime=regime_name,
            signal_source=signal_source,
            score_adjustments=adjustments + list((regime or {}).get("adjustments") or []) + list((korean_market or {}).get("reasons") or []),
            hold_reasons=hold_reasons,
            buy_score_zone=self.buy_score_zone(final_buy),
            sell_score_zone=self.sell_score_zone(final_sell),
            risk_score_zone=self.risk_score_zone(adjusted_risk),
            score_zone=self.buy_score_zone(final_buy) if final_buy >= final_sell else self.sell_score_zone(final_sell),
            signal_description=description,
            reasons=reasons,
            buy_factors=buy_factors,
            sell_factors=sell_factors,
        )

    def apply_ranked_signal(self, item: dict[str, Any], market_regime: str) -> dict[str, Any]:
        ranked = dict(item)
        buy_percentile = float(ranked.get("buy_score_percentile") or 0)
        sell_percentile = float(ranked.get("sell_score_percentile") or 0)
        risk_score = int(ranked.get("risk_score") or 0)
        liquidity_score = float(ranked.get("liquidity_score") or 0)

        if buy_percentile >= 95 and risk_score <= 55 and liquidity_score >= 60 and market_regime != "BEAR_CRASH":
            signal = "STRONG BUY"
        elif buy_percentile >= 85 and risk_score <= 65:
            signal = "BUY"
        elif buy_percentile >= 70 and risk_score <= 75:
            signal = "WEAK BUY"
        elif sell_percentile >= 95:
            signal = "STRONG SELL"
        elif sell_percentile >= 85:
            signal = "SELL"
        elif sell_percentile >= 70:
            signal = "WEAK SELL"
        else:
            signal = "HOLD"

        hold_reasons = self._rank_hold_reasons(ranked, market_regime) if signal == "HOLD" else []
        ranked["signal"] = signal
        ranked["market_regime"] = market_regime
        ranked["signal_source"] = "relative_rank_regime_ml"
        ranked["signal_description"] = self._rank_signal_description(signal, ranked, market_regime)
        ranked["hold_reasons"] = hold_reasons
        ranked["reasons"] = self._rank_reasons(ranked, hold_reasons)
        return ranked

    def score_row(self, current: pd.Series, previous: pd.Series, risk_score: int = 0) -> SignalScore:
        frame = pd.DataFrame([previous, current]).reset_index(drop=True)
        return self.score(frame, risk_score, prediction=None)

    def buy_score_zone(self, score: int) -> str:
        if score >= 90:
            return "강한 매수 구간"
        if score >= 75:
            return "매수 구간"
        if score >= 60:
            return "약한 매수 구간"
        if score >= 40:
            return "관망"
        return "매수 부적합"

    def sell_score_zone(self, score: int) -> str:
        if score >= 90:
            return "강한 매도 구간"
        if score >= 75:
            return "매도 구간"
        if score >= 60:
            return "약한 매도 구간"
        if score >= 40:
            return "관망"
        return "매도 신호 약함"

    def risk_score_zone(self, score: int) -> str:
        if score <= 30:
            return "낮음"
        if score <= 60:
            return "보통"
        if score <= 80:
            return "높음"
        return "매우 높음"

    def _raw_scores(self, enriched: pd.DataFrame) -> tuple[int, int, list[str], list[str]]:
        latest = enriched.iloc[-1]
        previous = enriched.iloc[-2] if len(enriched) > 1 else latest
        buy_score = 0
        sell_score = 0
        buy_factors: list[str] = []
        sell_factors: list[str] = []

        buy_score += self._add(latest["rsi"] < 30, 18, buy_factors, "RSI가 과매도 구간에 가까워 반등 가능성이 높아졌습니다.")
        buy_score += self._add(30 <= latest["rsi"] < 40, 8, buy_factors, "RSI가 낮은 중립권으로 가격 부담이 일부 완화되었습니다.")
        sell_score += self._add(latest["rsi"] > 70, 18, sell_factors, "RSI가 과매수 구간에 가까워 단기 과열 부담이 있습니다.")

        golden_cross = previous["ma5"] <= previous["ma20"] and latest["ma5"] > latest["ma20"]
        dead_cross = previous["ma5"] >= previous["ma20"] and latest["ma5"] < latest["ma20"]
        buy_score += self._add(golden_cross, 18, buy_factors, "MA5가 MA20을 상향 돌파해 단기 추세가 개선되었습니다.")
        buy_score += self._add(not golden_cross and latest["ma5"] > latest["ma20"], 8, buy_factors, "MA5가 MA20 위에 있어 단기 흐름이 우호적입니다.")
        sell_score += self._add(dead_cross, 18, sell_factors, "MA5가 MA20을 하향 이탈해 단기 추세가 약화되었습니다.")
        sell_score += self._add(not dead_cross and latest["ma5"] < latest["ma20"], 8, sell_factors, "MA5가 MA20 아래에 있어 약세 흐름이 남아 있습니다.")

        macd_golden = previous["macd"] <= previous["macd_signal"] and latest["macd"] > latest["macd_signal"]
        macd_dead = previous["macd"] >= previous["macd_signal"] and latest["macd"] < latest["macd_signal"]
        buy_score += self._add(macd_golden, 16, buy_factors, "MACD 골든크로스가 발생해 모멘텀이 개선되었습니다.")
        buy_score += self._add(not macd_golden and latest["macd"] > latest["macd_signal"], 6, buy_factors, "MACD가 시그널 위에 있어 매수 쪽 모멘텀이 있습니다.")
        sell_score += self._add(macd_dead, 16, sell_factors, "MACD 데드크로스가 발생해 모멘텀이 약화되었습니다.")
        sell_score += self._add(not macd_dead and latest["macd"] < latest["macd_signal"], 6, sell_factors, "MACD가 시그널 아래에 있어 매도 압력이 남아 있습니다.")

        band_position = self._band_position(latest)
        buy_score += self._add(band_position < 0.2, 12, buy_factors, "현재가가 Bollinger Band 하단에 가까워 반등 후보로 볼 수 있습니다.")
        sell_score += self._add(band_position > 0.8, 12, sell_factors, "현재가가 Bollinger Band 상단에 가까워 단기 부담이 있습니다.")

        buy_score += self._add(latest["volume_change"] > 20, 10, buy_factors, "거래량이 증가해 가격 움직임의 신뢰도가 높아졌습니다.")
        sell_score += self._add(latest["return_5d"] > 7 and latest["volume_change"] < -10, 12, sell_factors, "최근 급등 이후 거래량이 줄어 추세 둔화 가능성이 있습니다.")

        rebound = latest["return_1d"] > 0 and latest["return_5d"] < 0 and latest["close"] > previous["close"]
        buy_score += self._add(rebound, 10, buy_factors, "최근 하락 후 반등 흐름이 나타났습니다.")

        resistance_fail = latest["high"] >= latest["recent_high"] * 0.995 and latest["close"] < latest["recent_high"] and latest["return_1d"] <= 0
        sell_score += self._add(resistance_fail, 10, sell_factors, "저항선 부근에서 돌파 실패 가능성이 관찰됩니다.")

        return min(100, int(buy_score)), min(100, int(sell_score)), buy_factors, sell_factors

    def _detail_signal(self, buy_score: int, sell_score: int, risk_score: int, ml_probability: float | None) -> str:
        if buy_score >= 85 and risk_score <= 55 and (ml_probability is None or ml_probability >= 0.60):
            return "STRONG BUY"
        if buy_score >= 75 and risk_score <= 65:
            return "BUY"
        if buy_score >= 60 and risk_score <= 75:
            return "WEAK BUY"
        if sell_score >= 85:
            return "STRONG SELL"
        if sell_score >= 75:
            return "SELL"
        if sell_score >= 60:
            return "WEAK SELL"
        return "HOLD"

    def _apply_regime_adjustment(
        self,
        regime_name: str,
        buy_score: float,
        sell_score: float,
        risk_score: float,
        adjustments: list[str],
    ) -> tuple[float, float, float]:
        if regime_name == "BULL_TREND":
            buy_score += 6
            adjustments.append("상승 추세 국면이라 추세형 매수 점수를 보강했습니다.")
        elif regime_name == "RECOVERY":
            buy_score += 5
            adjustments.append("회복 국면이라 반등형 점수를 보강했습니다.")
        elif regime_name == "SIDEWAYS":
            buy_score += 2
            adjustments.append("횡보장에서는 평균회귀형 반등 점수를 일부 반영했습니다.")
        elif regime_name == "BEAR_TREND":
            buy_score -= 8
            risk_score += 6
            sell_score += 4
            adjustments.append("하락 추세 국면이라 매수 기준을 강화했습니다.")
        elif regime_name == "HIGH_VOLATILITY":
            buy_score -= 10
            risk_score += 10
            adjustments.append("고변동성 국면이라 리스크 반영을 강화했습니다.")
        elif regime_name == "BEAR_CRASH":
            buy_score -= 18
            risk_score += 15
            sell_score += 8
            adjustments.append("급락장에서는 대부분의 매수 신호를 보수적으로 낮춥니다.")
        return buy_score, sell_score, risk_score

    def _signal_description(self, signal: str, buy_score: int, sell_score: int, risk_score: int, ml_probability: float | None, signal_source: str) -> str:
        probability_text = f" ML 상승확률은 {ml_probability * 100:.0f}%입니다." if ml_probability is not None else " ML 상승확률은 데이터 부족으로 제외했습니다."
        if signal in {"STRONG BUY", "BUY", "WEAK BUY"}:
            return f"최종 매수 점수 {buy_score}점과 리스크 {risk_score}점을 기준으로 {signal}로 분류했습니다.{probability_text}"
        if signal in {"STRONG SELL", "SELL", "WEAK SELL"}:
            return f"최종 매도 점수 {sell_score}점이 기준을 충족해 {signal}로 분류했습니다.{probability_text}"
        return f"최종 매수 {buy_score}점, 최종 매도 {sell_score}점, 리스크 {risk_score}점이 적극 신호 기준을 충족하지 않아 HOLD로 분류했습니다.{probability_text}"

    def _rank_signal_description(self, signal: str, item: dict[str, Any], market_regime: str) -> str:
        if signal in {"STRONG BUY", "BUY", "WEAK BUY"}:
            return f"매수 점수 상대 순위가 상위권({item.get('buy_score_percentile', 0):.1f} percentile)이고 리스크 조건을 통과해 {signal}로 분류했습니다."
        if signal in {"STRONG SELL", "SELL", "WEAK SELL"}:
            return f"매도 점수 상대 순위가 상위권({item.get('sell_score_percentile', 0):.1f} percentile)이어서 {signal}로 분류했습니다."
        return f"상대 순위 또는 리스크 조건이 부족해 HOLD로 분류했습니다. 현재 시장국면은 {market_regime}입니다."

    def _rank_hold_reasons(self, item: dict[str, Any], market_regime: str) -> list[str]:
        reasons: list[str] = []
        if float(item.get("buy_score_percentile") or 0) >= 70 and int(item.get("risk_score") or 0) > 75:
            reasons.append("매수 점수 상대순위는 높지만 리스크 점수가 높아 HOLD로 분류했습니다.")
        if float(item.get("buy_score_percentile") or 0) >= 70 and float(item.get("liquidity_score") or 0) < 60:
            reasons.append("상대강도는 양호하지만 유동성 확인이 부족합니다.")
        if market_regime in {"BEAR_TREND", "HIGH_VOLATILITY", "BEAR_CRASH"}:
            reasons.append("시장국면이 약세 또는 고변동성이라 매수 기준이 강화되었습니다.")
        if not reasons:
            reasons.append("매수/매도 상대순위가 적극 신호 기준에 아직 도달하지 않았습니다.")
        return reasons

    def _rank_reasons(self, item: dict[str, Any], hold_reasons: list[str]) -> list[str]:
        if item["signal"] == "HOLD":
            return hold_reasons
        reasons = [
            f"매수 percentile {item.get('buy_score_percentile', 0):.1f}, 매도 percentile {item.get('sell_score_percentile', 0):.1f}, 리스크 {item.get('risk_score', 0)}점입니다.",
            item.get("signal_description", ""),
        ]
        reasons.extend(list(item.get("score_adjustments") or [])[:2])
        return [reason for reason in reasons if reason]

    def _hold_reasons(
        self,
        signal: str,
        buy_score: int,
        sell_score: int,
        risk_score: int,
        ml_probability: float | None,
        regime_name: str,
        liquidity_score: float | None,
    ) -> list[str]:
        if signal != "HOLD":
            return []
        reasons: list[str] = []
        if buy_score >= 60 and risk_score > 75:
            reasons.append("매수 점수는 높지만 리스크 점수가 높아 HOLD로 분류되었습니다.")
        if ml_probability is not None and ml_probability < 0.55 and buy_score >= 55:
            reasons.append("기술적 점수는 일부 우호적이지만 ML 상승확률이 충분히 높지 않습니다.")
        if liquidity_score is not None and liquidity_score < 35:
            reasons.append("거래량과 거래대금 확인이 부족해 적극 신호를 제한했습니다.")
        if regime_name in {"BEAR_TREND", "HIGH_VOLATILITY", "BEAR_CRASH"}:
            reasons.append("시장국면이 약세 또는 고변동성이라 매수 기준이 강화되었습니다.")
        if not reasons:
            reasons.append("매수와 매도 어느 쪽도 충분한 우위가 확인되지 않았습니다.")
        return reasons

    def _reasons(
        self,
        signal: str,
        buy_score: int,
        sell_score: int,
        risk_score: int,
        buy_factors: list[str],
        sell_factors: list[str],
        description: str,
        hold_reasons: list[str],
    ) -> list[str]:
        reasons = [
            f"최종 신호는 {signal}입니다. 최종 매수 {buy_score}점, 최종 매도 {sell_score}점, 리스크 {risk_score}점을 함께 반영했습니다.",
            description,
        ]
        if signal == "HOLD":
            reasons.extend(hold_reasons[:3])
        else:
            dominant = buy_factors if buy_score >= sell_score else sell_factors
            reasons.extend(dominant[:3])
        if risk_score >= 60:
            reasons.append("리스크 점수가 높아 신호 해석 시 보수적인 접근이 필요합니다.")
        return reasons

    def _ml_probability(self, ml_signal: dict[str, Any] | None) -> float | None:
        value = (ml_signal or {}).get("ml_up_probability")
        if value is None:
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    def _add(self, condition: bool, points: int, factors: list[str], reason: str) -> int:
        if bool(condition):
            factors.append(reason)
            return points
        return 0

    def _band_position(self, latest: pd.Series) -> float:
        lower = float(latest["bollinger_lower"])
        upper = float(latest["bollinger_upper"])
        close = float(latest["close"])
        width = max(upper - lower, 1e-9)
        return (close - lower) / width

    def _soft_cap(self, x: float, knee: float = 85.0, ceiling: float = 100.0) -> float:
        """knee 초과분을 지수적으로 압축해 ceiling에 점근. 순서 보존.
        예: 85→85, 100→~94, 132→~99.7. 다중 보정 덧셈의 100점 천장 쏠림 완화."""
        if x <= knee:
            return x
        span = ceiling - knee
        import math
        return knee + span * (1 - math.exp(-(x - knee) / span))

    def _clamp(self, value: float) -> int:
        return max(0, min(100, int(round(value))))
