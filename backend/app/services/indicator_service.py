from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.analysis import IndicatorDetail, SupportResistance


class IndicatorService:
    def enrich(self, prices: pd.DataFrame) -> pd.DataFrame:
        df = prices.copy().sort_values("date").reset_index(drop=True)
        if df.empty:
            return df

        df["ma5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["ma20"] = df["close"].rolling(window=20, min_periods=1).mean()
        df["ma60"] = df["close"].rolling(window=60, min_periods=1).mean()
        df["ma120"] = df["close"].rolling(window=120, min_periods=1).mean()
        df["rsi"] = self._rsi(df["close"])
        df["macd"], df["macd_signal"] = self._macd(df["close"])

        rolling_mean = df["close"].rolling(window=20, min_periods=1).mean()
        rolling_std = df["close"].rolling(window=20, min_periods=1).std().fillna(0)
        df["bollinger_upper"] = rolling_mean + rolling_std * 2
        df["bollinger_lower"] = rolling_mean - rolling_std * 2
        df["volume_change"] = df["volume"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        df["return_1d"] = df["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        df["return_5d"] = df["close"].pct_change(5).replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        df["volatility"] = df["return_1d"].rolling(window=20, min_periods=2).std().fillna(0)
        df["recent_high"] = df["high"].rolling(window=20, min_periods=1).max()
        df["recent_low"] = df["low"].rolling(window=20, min_periods=1).min()
        return df

    def summarize(self, enriched: pd.DataFrame) -> tuple[list[IndicatorDetail], SupportResistance]:
        if enriched.empty:
            raise ValueError("지표를 계산할 가격 데이터가 없습니다.")

        latest = enriched.iloc[-1]
        previous = enriched.iloc[-2] if len(enriched) > 1 else latest
        levels = self.support_resistance(enriched)
        indicators = [
            self._ma_detail("MA5", latest["ma5"], latest["close"], "단기 이동평균선"),
            self._ma_detail("MA20", latest["ma20"], latest["close"], "월간 이동평균선"),
            self._ma_detail("MA60", latest["ma60"], latest["close"], "분기 이동평균선"),
            self._ma_detail("MA120", latest["ma120"], latest["close"], "장기 이동평균선"),
            self._rsi_detail(latest["rsi"]),
            self._macd_detail(latest["macd"], latest["macd_signal"], previous["macd"], previous["macd_signal"]),
            self._bollinger_detail(latest),
            self._volume_detail(latest["volume_change"]),
            self._volatility_detail(latest["volatility"]),
            IndicatorDetail(
                name="최근 고점",
                value=round(float(levels.recent_high), 2),
                interpretation="최근 20거래일 기준 상단 가격 영역입니다.",
                influence="중립",
                contribution=0,
            ),
            IndicatorDetail(
                name="최근 저점",
                value=round(float(levels.recent_low), 2),
                interpretation="최근 20거래일 기준 하단 가격 영역입니다.",
                influence="중립",
                contribution=0,
            ),
            IndicatorDetail(
                name="지지선 후보",
                value=", ".join(f"{level:,.2f}" for level in levels.support),
                interpretation="최근 저점과 거래 구간을 기반으로 추정한 하단 방어 가격 후보입니다.",
                influence="매수" if levels.support else "중립",
                contribution=4 if levels.support else 0,
            ),
            IndicatorDetail(
                name="저항선 후보",
                value=", ".join(f"{level:,.2f}" for level in levels.resistance),
                interpretation="최근 고점과 거래 구간을 기반으로 추정한 상단 부담 가격 후보입니다.",
                influence="매도" if levels.resistance else "중립",
                contribution=-4 if levels.resistance else 0,
            ),
        ]
        return indicators, levels

    def support_resistance(self, enriched: pd.DataFrame) -> SupportResistance:
        window = enriched.tail(min(90, len(enriched)))
        recent = enriched.tail(min(20, len(enriched)))
        recent_high = float(recent["high"].max())
        recent_low = float(recent["low"].min())

        support_candidates = [
            float(window["low"].quantile(0.10)),
            float(window["low"].quantile(0.25)),
            float(recent_low),
        ]
        resistance_candidates = [
            float(window["high"].quantile(0.75)),
            float(window["high"].quantile(0.90)),
            float(recent_high),
        ]
        return SupportResistance(
            support=self._dedupe_levels(support_candidates),
            resistance=self._dedupe_levels(resistance_candidates),
            recent_high=round(recent_high, 2),
            recent_low=round(recent_low, 2),
        )

    def _rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _macd(self, close: pd.Series) -> tuple[pd.Series, pd.Series]:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def _dedupe_levels(self, levels: list[float]) -> list[float]:
        cleaned: list[float] = []
        for level in sorted([round(value, 2) for value in levels if np.isfinite(value)]):
            if not cleaned or abs(level - cleaned[-1]) / max(cleaned[-1], 1) > 0.015:
                cleaned.append(level)
        return cleaned[:3]

    def _ma_detail(self, name: str, ma_value: float, close: float, label: str) -> IndicatorDetail:
        diff_pct = (close - ma_value) / ma_value * 100 if ma_value else 0
        if diff_pct > 1:
            interpretation = f"현재가가 {label} 위에 있어 상승 흐름이 우세합니다."
            influence = "매수"
            contribution = min(10, int(abs(diff_pct)))
        elif diff_pct < -1:
            interpretation = f"현재가가 {label} 아래에 있어 약세 부담이 있습니다."
            influence = "매도"
            contribution = -min(10, int(abs(diff_pct)))
        else:
            interpretation = f"현재가가 {label} 부근에 있어 방향성 확인이 필요합니다."
            influence = "중립"
            contribution = 0
        return IndicatorDetail(
            name=name,
            value=round(float(ma_value), 2),
            interpretation=interpretation,
            influence=influence,
            contribution=contribution,
        )

    def _rsi_detail(self, rsi: float) -> IndicatorDetail:
        value = round(float(rsi), 2)
        if value < 30:
            return IndicatorDetail(name="RSI", value=value, interpretation="과매도 구간에 가까워 반등 가능성을 점검할 수 있습니다.", influence="매수", contribution=16)
        if value > 70:
            return IndicatorDetail(name="RSI", value=value, interpretation="과매수 구간에 가까워 단기 과열 부담이 있습니다.", influence="매도", contribution=-16)
        return IndicatorDetail(name="RSI", value=value, interpretation="중립 구간으로 추세 확인이 더 중요합니다.", influence="중립", contribution=0)

    def _macd_detail(self, macd: float, signal: float, prev_macd: float, prev_signal: float) -> IndicatorDetail:
        crossed_up = prev_macd <= prev_signal and macd > signal
        crossed_down = prev_macd >= prev_signal and macd < signal
        if crossed_up:
            return IndicatorDetail(name="MACD", value=round(float(macd), 4), interpretation="MACD가 시그널을 상향 돌파해 단기 모멘텀이 개선되었습니다.", influence="매수", contribution=14)
        if crossed_down:
            return IndicatorDetail(name="MACD", value=round(float(macd), 4), interpretation="MACD가 시그널을 하향 이탈해 단기 모멘텀이 약화되었습니다.", influence="매도", contribution=-14)
        if macd > signal:
            return IndicatorDetail(name="MACD", value=round(float(macd), 4), interpretation="MACD가 시그널 위에 있어 우호적인 흐름입니다.", influence="매수", contribution=6)
        return IndicatorDetail(name="MACD", value=round(float(macd), 4), interpretation="MACD가 시그널 아래에 있어 모멘텀 확인이 필요합니다.", influence="매도", contribution=-6)

    def _bollinger_detail(self, latest: pd.Series) -> IndicatorDetail:
        close = float(latest["close"])
        upper = float(latest["bollinger_upper"])
        lower = float(latest["bollinger_lower"])
        width = max(upper - lower, 1e-9)
        position = (close - lower) / width
        if position < 0.2:
            interpretation = "현재가가 볼린저밴드 하단에 가까워 단기 반등 가능성을 점검할 수 있습니다."
            return IndicatorDetail(name="Bollinger Bands", value=f"{lower:,.2f} ~ {upper:,.2f}", interpretation=interpretation, influence="매수", contribution=10)
        if position > 0.8:
            interpretation = "현재가가 볼린저밴드 상단에 가까워 단기 과열 부담이 있습니다."
            return IndicatorDetail(name="Bollinger Bands", value=f"{lower:,.2f} ~ {upper:,.2f}", interpretation=interpretation, influence="매도", contribution=-10)
        return IndicatorDetail(name="Bollinger Bands", value=f"{lower:,.2f} ~ {upper:,.2f}", interpretation="현재가가 밴드 중앙권에 있어 변동성 돌파 신호는 제한적입니다.", influence="중립", contribution=0)

    def _volume_detail(self, volume_change: float) -> IndicatorDetail:
        value = round(float(volume_change), 2)
        if value > 20:
            return IndicatorDetail(name="거래량 변화율", value=value, interpretation="거래량이 의미 있게 증가해 가격 움직임의 신뢰도를 높입니다.", influence="매수", contribution=8)
        if value < -30:
            return IndicatorDetail(name="거래량 변화율", value=value, interpretation="거래량이 급감해 추세 지속성에 대한 확인이 필요합니다.", influence="매도", contribution=-6)
        return IndicatorDetail(name="거래량 변화율", value=value, interpretation="거래량 변화가 크지 않아 중립적으로 해석합니다.", influence="중립", contribution=0)

    def _volatility_detail(self, volatility: float) -> IndicatorDetail:
        value = round(float(volatility), 2)
        if value > 3:
            return IndicatorDetail(name="변동성", value=value, interpretation="최근 일간 변동성이 높아 포지션 규모와 손실 관리가 중요합니다.", influence="매도", contribution=-10)
        if value < 1:
            return IndicatorDetail(name="변동성", value=value, interpretation="최근 변동성이 낮아 급격한 가격 흔들림은 제한적입니다.", influence="중립", contribution=2)
        return IndicatorDetail(name="변동성", value=value, interpretation="일반적인 변동성 구간입니다.", influence="중립", contribution=0)
