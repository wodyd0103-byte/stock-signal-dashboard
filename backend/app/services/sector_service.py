"""
업종/섹터 상대강도 서비스.

종목의 20일 수익률을 동종업종 peer 중앙값과 비교 → 섹터 내 상대강도.
- peer 목록: 네이버 integration API (industryCompareInfo)
- peer OHLCV: data_provider (캐시 활용, 병렬)
- 결과: sector_rs (종목 - peer중앙값, %p), percentile, 0~100 점수
캐시: 30분.
"""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock

import numpy as np
import requests

logger = logging.getLogger("sector")

_cache: dict[str, tuple[float, "SectorStrength"]] = {}
_cache_lock = Lock()
_TTL = 1800
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _is_kr(t: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", t.strip()))


@dataclass
class SectorStrength:
    ticker: str
    stock_return_20d: float
    peer_median_20d: float
    sector_rs: float          # 종목 - peer중앙값 (%p)
    percentile: float         # 섹터 내 백분위 (0~100)
    score: float              # 0~100 (signal 가산용)
    peer_count: int
    summary: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "stock_return_20d": round(self.stock_return_20d, 2),
            "peer_median_20d": round(self.peer_median_20d, 2),
            "sector_rs": round(self.sector_rs, 2),
            "percentile": round(self.percentile, 1),
            "score": round(self.score, 1),
            "peer_count": self.peer_count,
            "summary": self.summary,
        }


class SectorService:
    def __init__(self, data_provider):
        self.data_provider = data_provider

    def get(self, ticker: str) -> SectorStrength | None:
        ticker = ticker.strip()
        if not _is_kr(ticker):
            return None
        with _cache_lock:
            hit = _cache.get(ticker)
        if hit and (time.time() - hit[0]) < _TTL:
            return hit[1]
        try:
            res = self._compute(ticker)
        except Exception as exc:
            logger.warning(f"섹터 상대강도 실패 {ticker}: {exc}")
            return None
        if res:
            with _cache_lock:
                _cache[ticker] = (time.time(), res)
        return res

    def _ret20(self, tk: str) -> float | None:
        try:
            r = self.data_provider.fetch_ohlcv(tk, "3mo")
            df = r.data
            if df is None or len(df) < 21:
                return None
            c = df["close"].astype(float)
            return float(c.iloc[-1] / c.iloc[-21] - 1) * 100
        except Exception:
            return None

    def _peers(self, ticker: str) -> list[str]:
        url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
        d = requests.get(url, headers=_HEADERS, timeout=8).json()
        peers = d.get("industryCompareInfo", []) or []
        codes = [p.get("itemCode") for p in peers if _is_kr(str(p.get("itemCode", "")))]
        return [c for c in codes if c and c != ticker][:8]

    def _compute(self, ticker: str) -> SectorStrength | None:
        peers = self._peers(ticker)
        if len(peers) < 2:
            return None

        # 종목 + peer 20일 수익률 병렬 수집
        targets = [ticker] + peers
        rets: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=min(6, len(targets))) as ex:
            futs = {ex.submit(self._ret20, t): t for t in targets}
            for f, t in futs.items():
                v = f.result()
                if v is not None:
                    rets[t] = v

        if ticker not in rets:
            return None
        peer_rets = [v for k, v in rets.items() if k != ticker]
        if len(peer_rets) < 2:
            return None

        stock_ret = rets[ticker]
        peer_median = float(np.median(peer_rets))
        sector_rs = stock_ret - peer_median
        # percentile: 종목이 peer 대비 몇 % 상위인가
        all_rets = peer_rets + [stock_ret]
        rank = sum(1 for r in all_rets if r <= stock_ret)
        percentile = rank / len(all_rets) * 100
        # 점수: percentile 기반 50 중심
        score = max(0.0, min(100.0, percentile))

        summary = (
            f"섹터 내 20일 수익률 {stock_ret:+.1f}% vs 동종업종 중앙값 {peer_median:+.1f}% "
            f"(상대강도 {sector_rs:+.1f}%p, 상위 {100 - percentile:.0f}%)"
        )
        return SectorStrength(
            ticker=ticker, stock_return_20d=stock_ret, peer_median_20d=peer_median,
            sector_rs=sector_rs, percentile=percentile, score=score,
            peer_count=len(peer_rets), summary=summary,
        )
