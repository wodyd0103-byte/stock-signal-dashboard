"""
회고 서비스 — 추천 기록 + N일 후 실제 성과 채점.

흐름:
1. 매수 신호(BUY 계열) 분석 시 record() → DB 저장 (중복 방지: 같은 종목 24h 내 1회)
2. evaluate_due() → horizon 경과한 open 추천을 현재가로 채점
3. summary() → 적중률/평균수익 집계

적중 기준: 매수 신호였고 horizon 후 수익률 > 0.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation

logger = logging.getLogger("retrospective")

_BUY_SIGNALS = {"STRONG BUY", "BUY", "WEAK BUY"}
_DEDUP_HOURS = 24


class RetrospectiveService:
    def record(
        self, db: Session, *, ticker: str, name: str | None, market: str | None,
        signal: str, buy_score: int, risk_score: int, price: float, horizon_days: int = 5,
    ) -> Recommendation | None:
        """매수 신호만 기록. 24h 내 같은 종목 중복 방지."""
        if signal not in _BUY_SIGNALS:
            return None
        cutoff = datetime.utcnow() - timedelta(hours=_DEDUP_HOURS)
        dup = db.execute(
            select(Recommendation).where(
                Recommendation.ticker == ticker,
                Recommendation.recommended_at >= cutoff,
            )
        ).scalars().first()
        if dup:
            return dup
        rec = Recommendation(
            ticker=ticker, name=name, market=market,
            signal=signal, buy_score=buy_score, risk_score=risk_score,
            price_at_rec=price, horizon_days=horizon_days, status="open",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    def evaluate_due(self, db: Session, price_fn) -> int:
        """horizon 경과한 open 추천 채점. 채점 건수 반환.

        `price_fn(ticker, due_date) -> float | None` 은 **그 시점의** 종가를 준다.
        현재가로 재면 늦게 채점할수록 숫자가 부풀어 오른다 — horizon 5일짜리를
        71일 뒤에 채점하면 71일 수익률이 5일 성과로 남는다. 적중률과 평균수익이
        그 숫자 위에 쌓이므로 시점을 지키는 것이 이 기능의 전제다.
        """
        now = datetime.utcnow()
        open_recs = db.execute(
            select(Recommendation).where(Recommendation.status == "open")
        ).scalars().all()
        evaluated = 0
        for rec in open_recs:
            due = rec.recommended_at + timedelta(days=rec.horizon_days)
            if now < due:
                continue
            try:
                price_after = price_fn(rec.ticker, due.date())
            except Exception:
                price_after = None
            if price_after is None or rec.price_at_rec <= 0:
                continue
            ret = (price_after - rec.price_at_rec) / rec.price_at_rec * 100
            rec.price_after = round(float(price_after), 2)
            rec.return_pct = round(float(ret), 2)
            rec.hit = 1 if ret > 0 else 0
            rec.evaluated_at = now
            rec.status = "evaluated"
            evaluated += 1
        if evaluated:
            db.commit()
        return evaluated

    def summary(self, db: Session) -> dict:
        recs = db.execute(select(Recommendation)).scalars().all()
        evaluated = [r for r in recs if r.status == "evaluated" and r.return_pct is not None]
        open_count = sum(1 for r in recs if r.status == "open")
        n = len(evaluated)
        if n == 0:
            return {
                "total": len(recs), "evaluated": 0, "open": open_count,
                "hit_rate": None, "avg_return": None, "avg_win": None, "avg_loss": None,
                "by_signal": [], "recent": [r_to_dict(r) for r in sorted(recs, key=lambda x: x.recommended_at, reverse=True)[:20]],
            }
        hits = sum(r.hit or 0 for r in evaluated)
        wins = [r.return_pct for r in evaluated if (r.return_pct or 0) > 0]
        losses = [r.return_pct for r in evaluated if (r.return_pct or 0) <= 0]
        # 신호별 집계
        by_sig: dict[str, list] = {}
        for r in evaluated:
            by_sig.setdefault(r.signal, []).append(r)
        by_signal = [
            {
                "signal": sig,
                "count": len(rs),
                "hit_rate": round(sum(x.hit or 0 for x in rs) / len(rs), 3),
                "avg_return": round(sum(x.return_pct or 0 for x in rs) / len(rs), 2),
            }
            for sig, rs in sorted(by_sig.items())
        ]
        return {
            "total": len(recs),
            "evaluated": n,
            "open": open_count,
            "hit_rate": round(hits / n, 3),
            "avg_return": round(sum(r.return_pct or 0 for r in evaluated) / n, 2),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
            "by_signal": by_signal,
            "recent": [r_to_dict(r) for r in sorted(recs, key=lambda x: x.recommended_at, reverse=True)[:20]],
        }


def r_to_dict(r: Recommendation) -> dict:
    return {
        "id": r.id, "ticker": r.ticker, "name": r.name, "market": r.market,
        "signal": r.signal, "buy_score": r.buy_score, "risk_score": r.risk_score,
        "price_at_rec": r.price_at_rec, "recommended_at": r.recommended_at.isoformat(),
        "price_after": r.price_after, "return_pct": r.return_pct,
        "horizon_days": r.horizon_days, "hit": r.hit, "status": r.status,
        "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
    }
