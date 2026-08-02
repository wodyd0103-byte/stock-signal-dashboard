"""
수급 서비스 — 외국인/기관 순매매 (네이버금융 크롤링, KRX 인증 불필요).

한국시장 alpha 최강 factor. 6자리 종목코드만 지원.
점수: 외국인+기관 5일/20일 누적 순매수 → 0~100 수급 점수.
캐시: 30분.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

import pandas as pd
import requests

logger = logging.getLogger("supply_demand")

_cache: dict[str, tuple[datetime, "SupplyDemand"]] = {}
_cache_lock = Lock()
_TTL = 1800
_HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass
class SupplyDemand:
    ticker: str
    foreign_5d: float       # 외국인 5일 누적 순매매량 (주)
    foreign_20d: float
    inst_5d: float          # 기관 5일 누적
    inst_20d: float
    flow_score: float       # 0~100 (수급 점수, signal에 가산)
    buying: bool            # 외국인+기관 5일 순매수 여부
    summary: str
    foreign_hold_ratio: float | None = None  # 외국인 보유비율 (%)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "foreign_5d": int(self.foreign_5d),
            "foreign_20d": int(self.foreign_20d),
            "inst_5d": int(self.inst_5d),
            "inst_20d": int(self.inst_20d),
            "korean_flow_score": round(self.flow_score, 1),
            "buying": self.buying,
            "summary": self.summary,
            "foreign_hold_ratio": self.foreign_hold_ratio,
        }


def _is_kr(ticker: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", ticker.strip()))


class SupplyDemandService:
    def get(self, ticker: str) -> SupplyDemand | None:
        ticker = ticker.strip()
        if not _is_kr(ticker):
            return None
        with _cache_lock:
            cached = _cache.get(ticker)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < _TTL:
            return cached[1]
        try:
            sd = self._fetch(ticker)
        except Exception as exc:
            logger.warning(f"수급 수집 실패 {ticker}: {exc}")
            return None
        if sd:
            with _cache_lock:
                _cache[ticker] = (datetime.utcnow(), sd)
        return sd

    def _fetch(self, ticker: str) -> SupplyDemand | None:
        frames = []
        # 2페이지 (약 60거래일) 수집
        for page in (1, 2):
            url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"
            html = requests.get(url, headers=_HEADERS, timeout=10).text
            tables = pd.read_html(html)
            target = next((t for t in tables if t.shape[1] == 9 and t.shape[0] > 5), None)
            if target is not None:
                frames.append(target)
        if not frames:
            return None

        df = pd.concat(frames, ignore_index=True)
        # MultiIndex 컬럼 평탄화
        df.columns = [" ".join(str(x) for x in c).strip() if isinstance(c, tuple) else str(c) for c in df.columns]
        inst_col = next((c for c in df.columns if "기관" in c), None)
        foreign_col = next((c for c in df.columns if "외국인" in c), None)
        date_col = next((c for c in df.columns if "날짜" in c), None)
        if not inst_col or not foreign_col:
            return None

        df = df.dropna(subset=[date_col]) if date_col else df.dropna()
        df[inst_col] = pd.to_numeric(df[inst_col].astype(str).str.replace(",", ""), errors="coerce")
        df[foreign_col] = pd.to_numeric(df[foreign_col].astype(str).str.replace(",", ""), errors="coerce")
        df = df.dropna(subset=[inst_col, foreign_col]).reset_index(drop=True)
        if len(df) < 5:
            return None

        # 날짜 명시적 내림차순 정렬 → head(N)이 항상 최근 N일 (네이버 순서 가정 제거)
        if date_col:
            df["_d"] = pd.to_datetime(
                df[date_col].astype(str).str.replace(".", "-", regex=False),
                errors="coerce",
            )
            if df["_d"].notna().sum() >= 5:
                df = df.sort_values("_d", ascending=False).reset_index(drop=True)

        inst_5d = float(df[inst_col].head(5).sum())
        inst_20d = float(df[inst_col].head(20).sum())
        foreign_5d = float(df[foreign_col].head(5).sum())
        foreign_20d = float(df[foreign_col].head(20).sum())

        flow_score = self._score(foreign_5d, foreign_20d, inst_5d, inst_20d)
        buying = (foreign_5d + inst_5d) > 0
        summary = self._summary(foreign_5d, inst_5d, buying)
        hold_ratio = self._foreign_hold_ratio(ticker)

        return SupplyDemand(
            ticker=ticker,
            foreign_5d=foreign_5d, foreign_20d=foreign_20d,
            inst_5d=inst_5d, inst_20d=inst_20d,
            flow_score=flow_score, buying=buying, summary=summary,
            foreign_hold_ratio=hold_ratio,
        )

    def _foreign_hold_ratio(self, ticker: str) -> float | None:
        """외국인 보유비율 (네이버 모바일 trend API). 실패 시 None."""
        try:
            url = f"https://m.stock.naver.com/api/stock/{ticker}/trend"
            data = requests.get(url, headers=_HEADERS, timeout=8).json()
            row = data[0] if isinstance(data, list) and data else None
            if not row:
                return None
            raw = str(row.get("foreignerHoldRatio", "")).replace("%", "").strip()
            return float(raw) if raw else None
        except Exception:
            return None

    def _score(self, f5: float, f20: float, i5: float, i20: float) -> float:
        """순매수 방향 + 일관성 → 0~100. 평균거래량 정규화 대신 부호/조합 기반."""
        score = 50.0
        # 5일 외국인/기관 순매수 방향
        if f5 > 0: score += 12
        if i5 > 0: score += 10
        if f5 < 0: score -= 12
        if i5 < 0: score -= 10
        # 20일 추세 일관성
        if f20 > 0 and f5 > 0: score += 8   # 외국인 지속 매수
        if i20 > 0 and i5 > 0: score += 6   # 기관 지속 매수
        if f20 < 0 and f5 < 0: score -= 8
        # 쌍끌이 (외국인+기관 동시 순매수)
        if f5 > 0 and i5 > 0: score += 6
        if f5 < 0 and i5 < 0: score -= 6
        return max(0.0, min(100.0, score))

    def _summary(self, f5: float, i5: float, buying: bool) -> str:
        f = "순매수" if f5 > 0 else "순매도"
        i = "순매수" if i5 > 0 else "순매도"
        head = "쌍끌이 매수" if (f5 > 0 and i5 > 0) else "쌍끌이 매도" if (f5 < 0 and i5 < 0) else "혼조"
        return f"최근 5일 외국인 {f}({f5:+,.0f}주), 기관 {i}({i5:+,.0f}주) — {head}"
