"""
재무/펀더멘털 서비스 — PER/PBR/배당/52주 위치 (네이버, DART 키 불요).

네이버 integration API의 totalInfos에서 밸류에이션 지표 수집.
ROE는 PBR/PER로 근사(ROE ≈ PBR/PER, %). 펀더멘털 점수(저평가일수록 ↑).
캐시: 6시간 (재무는 자주 안 바뀜). 국내 종목만.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from threading import Lock

import requests

logger = logging.getLogger("fundamental")

_cache: dict[str, tuple[float, "Fundamental"]] = {}
_cache_lock = Lock()
_TTL = 6 * 3600
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _is_kr(t: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", t.strip()))


def _num(s) -> float | None:
    if s is None:
        return None
    raw = re.sub(r"[^\d.\-]", "", str(s))
    try:
        return float(raw) if raw not in ("", "-", ".") else None
    except ValueError:
        return None


@dataclass
class Fundamental:
    ticker: str
    per: float | None
    pbr: float | None
    eps: float | None
    bps: float | None
    dividend_yield: float | None
    roe_est: float | None          # PBR/PER 근사 (%)
    pos_52w: float | None          # 52주 범위 내 위치 (0~100%)
    score: float                   # 0~100 (저평가·고배당·고ROE일수록 ↑)
    summary: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "per": self.per, "pbr": self.pbr,
            "eps": self.eps, "bps": self.bps, "dividend_yield": self.dividend_yield,
            "roe_est": round(self.roe_est, 1) if self.roe_est is not None else None,
            "pos_52w": round(self.pos_52w, 0) if self.pos_52w is not None else None,
            "score": round(self.score, 1), "summary": self.summary,
        }


class FundamentalService:
    def get(self, ticker: str) -> Fundamental | None:
        ticker = ticker.strip()
        if not _is_kr(ticker):
            return None
        with _cache_lock:
            hit = _cache.get(ticker)
        if hit and (time.time() - hit[0]) < _TTL:
            return hit[1]
        try:
            f = self._fetch(ticker)
        except Exception as exc:
            logger.warning(f"재무 수집 실패 {ticker}: {exc}")
            return None
        if f:
            with _cache_lock:
                _cache[ticker] = (time.time(), f)
        return f

    def _fetch(self, ticker: str) -> Fundamental | None:
        url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
        d = requests.get(url, headers=_HEADERS, timeout=8).json()
        info = {it.get("code"): it.get("value") for it in d.get("totalInfos", [])}
        if not info:
            return None

        per = _num(info.get("per"))
        pbr = _num(info.get("pbr"))
        eps = _num(info.get("eps"))
        bps = _num(info.get("bps"))
        dy = _num(info.get("dividendYieldRatio"))
        close = _num(info.get("lastClosePrice"))
        hi52 = _num(info.get("highPriceOf52Weeks"))
        lo52 = _num(info.get("lowPriceOf52Weeks"))

        roe = (pbr / per * 100) if (per and pbr and per > 0) else None
        pos = ((close - lo52) / (hi52 - lo52) * 100) if (close and hi52 and lo52 and hi52 > lo52) else None

        score = self._score(per, pbr, dy, roe)
        summary = self._summary(per, pbr, dy, roe, pos)
        return Fundamental(ticker, per, pbr, eps, bps, dy, roe, pos, score, summary)

    def _score(self, per, pbr, dy, roe) -> float:
        """저PER·저PBR·고배당·고ROE → 높은 점수. 0~100."""
        s = 50.0
        if per is not None and per > 0:
            if per < 8: s += 12
            elif per < 12: s += 6
            elif per > 40: s -= 10
            elif per > 25: s -= 5
        if pbr is not None and pbr > 0:
            if pbr < 1: s += 12
            elif pbr < 1.5: s += 6
            elif pbr > 5: s -= 8
        if dy is not None:
            if dy >= 4: s += 8
            elif dy >= 2: s += 4
        if roe is not None:
            if roe >= 15: s += 10
            elif roe >= 10: s += 5
            elif roe < 3: s -= 6
        return max(0.0, min(100.0, s))

    def _summary(self, per, pbr, dy, roe, pos) -> str:
        parts = []
        if per is not None: parts.append(f"PER {per:.1f}")
        if pbr is not None: parts.append(f"PBR {pbr:.2f}")
        if roe is not None: parts.append(f"ROE(추정) {roe:.1f}%")
        if dy is not None: parts.append(f"배당 {dy:.2f}%")
        if pos is not None: parts.append(f"52주 위치 {pos:.0f}%")
        return " · ".join(parts) if parts else "재무 데이터 부족"
