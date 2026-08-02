"""
포트폴리오 분석 서비스 — 보유종목 손익 + 신호 + 집중도 + 리밸런싱 조언.

종목별: 현재가, 평가손익, 비중, 신호(경량: enrich+risk+signal), 리스크.
포트폴리오: 총손익, 집중도(HHI), 가중 리스크, 신호 분포.
조언: 집중·매도신호·고위험·저평가 룰 기반.

종목 신호는 경량 계산 (prediction/sentiment/news 제외) → 빠름. 병렬.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger("portfolio")

_SELL_SIGNALS = {"STRONG SELL", "SELL", "WEAK SELL"}
_BUY_SIGNALS = {"STRONG BUY", "BUY", "WEAK BUY"}


@dataclass
class HoldingAnalysis:
    ticker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    cost: float
    pnl: float
    pnl_pct: float
    weight: float            # 포트폴리오 내 비중 (%)
    signal: str
    buy_score: int
    risk_score: int
    error: str | None = None


@dataclass
class PortfolioReport:
    holdings: list[HoldingAnalysis]
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    concentration_hhi: float     # 0~1 (1=완전집중)
    top_weight: float            # 최대 비중 (%)
    weighted_risk: float         # 가중 평균 리스크
    signal_counts: dict
    advice: list[str] = field(default_factory=list)
    high_corr_pairs: list = field(default_factory=list)   # [{a, b, corr}] 고상관 쌍
    avg_corr: float = 0.0                                  # 보유종목 평균 상관계수

    def to_dict(self) -> dict:
        return {
            "holdings": [h.__dict__ for h in self.holdings],
            "total_cost": round(self.total_cost, 0),
            "total_value": round(self.total_value, 0),
            "total_pnl": round(self.total_pnl, 0),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "concentration_hhi": round(self.concentration_hhi, 3),
            "top_weight": round(self.top_weight, 1),
            "weighted_risk": round(self.weighted_risk, 1),
            "signal_counts": self.signal_counts,
            "advice": self.advice,
            "high_corr_pairs": self.high_corr_pairs,
            "avg_corr": self.avg_corr,
        }


class PortfolioService:
    def __init__(self, data_provider, indicator_service, risk_service, build_signal_fn):
        self.data_provider = data_provider
        self.indicator_service = indicator_service
        self.risk_service = risk_service
        self.build_signal_fn = build_signal_fn  # (result, period, enriched, risk_score) -> SignalScore

    def analyze(self, holdings: list) -> PortfolioReport:
        """holdings: [{ticker, name, quantity, avg_price}, ...]"""
        if not holdings:
            return PortfolioReport([], 0, 0, 0, 0, 0, 0, 0, {}, ["보유 종목을 입력하세요."])

        with ThreadPoolExecutor(max_workers=min(8, len(holdings))) as ex:
            results = list(ex.map(self._analyze_one, holdings))

        valid = [r for r in results if r.error is None]
        total_value = sum(r.market_value for r in valid)
        total_cost = sum(r.cost for r in valid)

        # 비중 계산
        for r in valid:
            r.weight = (r.market_value / total_value * 100) if total_value > 0 else 0.0

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
        weights = [r.weight / 100 for r in valid]
        hhi = sum(w * w for w in weights)
        top_weight = max((r.weight for r in valid), default=0.0)
        weighted_risk = sum(r.risk_score * (r.weight / 100) for r in valid)

        signal_counts: dict = {}
        for r in valid:
            signal_counts[r.signal] = signal_counts.get(r.signal, 0) + 1

        high_corr_pairs, avg_corr = self._correlation(valid) if len(valid) >= 2 else ([], 0.0)

        report = PortfolioReport(
            holdings=results,  # error 포함 전체
            total_cost=total_cost, total_value=total_value,
            total_pnl=total_pnl, total_pnl_pct=total_pnl_pct,
            concentration_hhi=hhi, top_weight=top_weight,
            weighted_risk=weighted_risk, signal_counts=signal_counts,
            high_corr_pairs=high_corr_pairs, avg_corr=avg_corr,
        )
        report.advice = self._advice(valid, hhi, top_weight, weighted_risk, total_pnl_pct, high_corr_pairs)
        return report

    def _correlation(self, valid) -> tuple[list[dict], float]:
        """보유종목 일수익률 상관행렬 → 고상관 쌍(>=0.7) + 평균 상관.

        고상관 종목은 동반 등락 → 분산효과 제한. provider 캐시 재사용.
        """
        rets: dict[str, pd.Series] = {}
        name_map: dict[str, str] = {}
        for r in valid:
            try:
                df = self.data_provider.fetch_ohlcv(r.ticker, "1y").data
                if df is None or len(df) < 60:
                    continue
                rets[r.ticker] = df.set_index("date")["close"].astype(float).pct_change().dropna()
                name_map[r.ticker] = r.name
            except Exception:
                continue
        if len(rets) < 2:
            return [], 0.0
        R = pd.DataFrame(rets).dropna()
        if len(R) < 40:
            return [], 0.0
        C = R.corr()
        cols = list(C.columns)
        pairs: list[dict] = []
        vals: list[float] = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                c = float(C.iloc[i, j])
                if np.isnan(c):
                    continue
                vals.append(c)
                if c >= 0.7:
                    pairs.append({"a": name_map[cols[i]], "b": name_map[cols[j]], "corr": round(c, 2)})
        pairs.sort(key=lambda p: p["corr"], reverse=True)
        avg = round(float(np.mean(vals)), 2) if vals else 0.0
        return pairs[:5], avg

    def _analyze_one(self, h: dict) -> HoldingAnalysis:
        ticker = str(h["ticker"]).strip().upper()
        qty = float(h["quantity"])
        avg = float(h["avg_price"])
        name = h.get("name") or ticker
        base = HoldingAnalysis(
            ticker=ticker, name=name, quantity=qty, avg_price=avg,
            current_price=0, market_value=0, cost=qty * avg, pnl=0, pnl_pct=0,
            weight=0, signal="HOLD", buy_score=0, risk_score=0,
        )
        try:
            result = self.data_provider.fetch_ohlcv(ticker, "1y")
            enriched = self.indicator_service.enrich(result.data)
            if enriched.empty:
                base.error = "데이터 없음"
                return base
            current = float(enriched.iloc[-1]["close"])
            risk = self.risk_service.analyze(result.ticker, "1y", enriched)
            signal = self.build_signal_fn(result, "1y", enriched, risk.risk_score)

            base.name = name if h.get("name") else result.ticker
            base.current_price = round(current, 2)
            base.market_value = qty * current
            base.cost = qty * avg
            base.pnl = base.market_value - base.cost
            base.pnl_pct = (base.pnl / base.cost * 100) if base.cost > 0 else 0.0
            base.signal = signal.signal
            base.buy_score = signal.buy_score
            base.risk_score = signal.risk_score
        except Exception as exc:
            base.error = str(exc)
            logger.warning(f"포트폴리오 종목 분석 실패 {ticker}: {exc}")
        return base

    def rebalance(
        self,
        holdings: list,
        cash: float = 0.0,
        strategy: str = "signal",
        max_weight: float = 0.35,
        cash_buffer_pct: float = 0.0,
        commission_rate: float = 0.00015,
        sell_tax_rate: float = 0.0018,
        custom_weights: dict[str, float] | None = None,
    ) -> dict:
        """
        목표 비중 → 종목별 매수/매도 수량(정수) 제안 + 예상 거래비용.
        strategy: equal / signal / risk_parity
        max_weight: 종목당 최대 목표비중 캡
        cash: 보유 현금 (투자 가능 자산에 합산)
        cash_buffer_pct: 현금으로 남길 비율 (0~1) → 주식 미투자 보존
        commission_rate: 위탁수수료 (매수·매도 양방)
        sell_tax_rate: 증권거래세 (매도만)
        custom_weights: {ticker: 비중(0~1)} 수동 지정 시 strategy/cap 무시하고 honor (합=1 정규화).
        """
        rep = self.analyze(holdings)
        valid = [h for h in rep.holdings if h.error is None]
        if not valid:
            return {"error": "분석 가능한 보유 종목이 없습니다.", "trades": []}

        cash = max(0.0, cash)
        total_assets = rep.total_value + cash
        if total_assets <= 0:
            return {"error": "투자 가능 자산이 0입니다.", "trades": []}

        buffer = max(0.0, min(0.9, cash_buffer_pct))
        investable = total_assets * (1 - buffer)  # 주식에 배분할 금액

        # 목표 비중 산출
        if custom_weights:
            # 수동 비중: 보유 종목에 한해 honor, 합=1 정규화 (cap 미적용)
            raw = {h.ticker: max(0.0, float(custom_weights.get(h.ticker, 0.0))) for h in valid}
            total = sum(raw.values())
            if total <= 0:
                raw = {h.ticker: 1.0 for h in valid}
                total = float(len(valid))
            target_w = {k: v / total for k, v in raw.items()}
            strategy = "custom"
        else:
            raw = {}
            for h in valid:
                if strategy == "equal":
                    raw[h.ticker] = 1.0
                elif strategy == "risk_parity":
                    raw[h.ticker] = 1.0 / max(h.risk_score, 10)
                else:  # signal
                    raw[h.ticker] = max(h.buy_score, 5)
            eff_cap = max(max_weight, 1.0 / len(valid))
            target_w = self._normalize_with_cap(raw, eff_cap)

        # 종목별 목표가치 + 갭
        plan = []
        for h in valid:
            if h.current_price <= 0:
                continue
            tw = target_w.get(h.ticker, 0.0)
            plan.append({"h": h, "tw": tw, "target_value": investable * tw,
                         "gap": investable * tw - h.market_value})

        commission = tax = 0.0
        buy_value = sell_value = 0.0
        shares_map: dict[str, int] = {}

        # 1단계: 매도 (과보유 → 목표, 정수 내림). 현금 확보 먼저.
        for p in plan:
            if p["gap"] >= 0:
                continue
            price = p["h"].current_price
            sell_shares = int((-p["gap"]) / price)          # 목표 초과분만큼 (내림 → 과매도 방지)
            sell_shares = min(sell_shares, int(p["h"].quantity))  # 보유 초과 매도 금지
            if sell_shares <= 0:
                continue
            v = sell_shares * price
            shares_map[p["h"].ticker] = -sell_shares
            sell_value += v
            commission += v * commission_rate
            tax += v * sell_tax_rate

        # 2단계: 매수 예산 = 기존현금 + 매도수령 - 비용 - 목표버퍼
        buffer_target = total_assets * buffer
        budget = cash + sell_value - (commission + tax) - buffer_target
        # 갭 큰 종목(저비중) 우선 매수
        for p in sorted([p for p in plan if p["gap"] > 0], key=lambda x: x["gap"], reverse=True):
            if budget <= 0:
                break
            price = p["h"].current_price
            want = int(p["gap"] / price)                    # 목표까지 (내림)
            afford = int(budget / (price * (1 + commission_rate)))  # 예산 내 (수수료 포함)
            buy_shares = max(0, min(want, afford))
            if buy_shares <= 0:
                continue
            v = buy_shares * price
            shares_map[p["h"].ticker] = buy_shares
            buy_value += v
            c = v * commission_rate
            commission += c
            budget -= (v + c)

        trades = []
        for p in plan:
            h = p["h"]
            ds = shares_map.get(h.ticker, 0)
            action = "buy" if ds > 0 else "sell" if ds < 0 else "hold"
            trades.append({
                "ticker": h.ticker, "name": h.name,
                "current_weight": round(h.weight, 1),
                "target_weight": round(p["tw"] * 100, 1),
                "current_price": h.current_price,
                "delta_shares": ds,
                "delta_value": round(ds * h.current_price, 0),
                "action": action,
                "signal": h.signal,
            })

        trades.sort(key=lambda t: t["delta_value"])
        total_cost = commission + tax
        # 매매 후 잔여 현금 추정 (매도수령 - 매수지출 - 비용 + 기존현금)
        residual_cash = cash + sell_value - buy_value - total_cost
        return {
            "strategy": strategy,
            "total_assets": round(total_assets, 0),
            "investable": round(investable, 0),
            "cash": round(cash, 0),
            "cash_buffer_pct": round(buffer * 100, 0),
            "max_weight": round(max_weight * 100, 0),
            "trades": trades,
            "buy_total": round(buy_value, 0),
            "sell_total": round(sell_value, 0),
            "est_commission": round(commission, 0),
            "est_tax": round(tax, 0),
            "est_cost_total": round(total_cost, 0),
            "residual_cash": round(residual_cash, 0),
            "note": "정수주·거래비용(수수료 0.015%, 매도세 0.18%) 반영 추정치. 실제 체결가/세율과 차이날 수 있으며, 매매는 외부 앱에서 본인 판단으로 수행하세요.",
        }

    def _normalize_with_cap(self, raw: dict, cap: float) -> dict:
        """가중치 정규화 + 종목당 cap 초과분 재분배 (반복)."""
        w = dict(raw)
        for _ in range(10):
            total = sum(w.values()) or 1.0
            w = {k: v / total for k, v in w.items()}
            over = {k: v for k, v in w.items() if v > cap}
            if not over:
                break
            # cap 초과분 → cap 고정, 나머지에 비례 재분배
            excess = sum(v - cap for v in over.values())
            under = {k: v for k, v in w.items() if v <= cap}
            under_sum = sum(under.values()) or 1.0
            for k in w:
                if k in over:
                    w[k] = cap
                else:
                    w[k] = w[k] + excess * (w[k] / under_sum)
        return w

    def _advice(self, valid, hhi, top_weight, weighted_risk, total_pnl_pct, high_corr_pairs=None) -> list[str]:
        advice: list[str] = []

        # 집중도
        if top_weight >= 40:
            advice.append(f"⚠️ 한 종목 비중이 {top_weight:.0f}%로 과도합니다. 분산을 검토하세요.")
        elif hhi >= 0.4:
            advice.append(f"집중도(HHI {hhi:.2f})가 높습니다. 종목 수를 늘려 분산을 고려하세요.")

        # 종목 수
        if len(valid) < 3:
            advice.append("종목 수가 적어 개별 종목 리스크에 노출됩니다.")

        # 상관 분산경고
        if high_corr_pairs:
            top = high_corr_pairs[0]
            extra = f" 외 {len(high_corr_pairs) - 1}쌍" if len(high_corr_pairs) > 1 else ""
            advice.append(
                f"🔗 {top['a']}·{top['b']} 상관 {top['corr']}{extra} (고상관). "
                "동반 하락 위험 — 보유 종목 수 대비 실제 분산효과가 낮습니다."
            )

        # 매도 신호 종목
        sell_holdings = [r for r in valid if r.signal in _SELL_SIGNALS]
        for r in sell_holdings:
            advice.append(f"📉 {r.name}({r.weight:.0f}%): 매도 신호({r.signal}). 비중 축소 검토.")

        # 고위험 + 손실 종목
        for r in valid:
            if r.risk_score >= 70 and r.pnl_pct < 0:
                advice.append(f"🔺 {r.name}: 리스크 {r.risk_score} + 손실 {r.pnl_pct:.1f}%. 손절 기준 점검.")

        # 가중 리스크
        if weighted_risk >= 65:
            advice.append(f"포트폴리오 가중 리스크가 {weighted_risk:.0f}로 높습니다. 방어적 비중 조정 고려.")

        # 강한 매수 + 저비중 (있으면 추가 검토 — 단정 회피)
        strong_low = [r for r in valid if r.signal == "STRONG BUY" and r.weight < 10]
        for r in strong_low[:2]:
            advice.append(f"📈 {r.name}({r.weight:.0f}%): 강한 매수 신호이나 비중 낮음. 추가 매수 검토 가능.")

        if not advice:
            advice.append("특이 위험 신호 없음. 정기적으로 신호와 비중을 점검하세요.")

        advice.append("※ 알고리즘 참고 정보입니다. 실제 매매·비중 조정은 본인 판단으로 외부 앱에서 수행하세요.")
        return advice
