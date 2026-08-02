"""
디스크 영속 캐시 (joblib pickle).

예측 결과 등 무거운 계산을 디스크에 저장 → 서버 재시작 후에도 재계산 회피.
키는 데이터 시그니처(ticker+period+행수+마지막종가)라 데이터 바뀌면 자동 무효.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from threading import Lock

import joblib

logger = logging.getLogger("disk_cache")

_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_lock = Lock()


def _path(namespace: str, key: tuple) -> Path:
    raw = repr(key).encode("utf-8")
    h = hashlib.sha1(raw).hexdigest()[:20]
    return _CACHE_DIR / f"{namespace}_{h}.pkl"


def get(namespace: str, key: tuple, ttl: float):
    """캐시 조회. 만료/없음 → None."""
    fp = _path(namespace, key)
    if not fp.exists():
        return None
    try:
        if (time.time() - fp.stat().st_mtime) > ttl:
            return None
        with _lock:
            payload = joblib.load(fp)
        return payload
    except Exception as exc:
        logger.warning(f"disk_cache load 실패 {fp.name}: {exc}")
        return None


def put(namespace: str, key: tuple, value) -> None:
    fp = _path(namespace, key)
    try:
        with _lock:
            joblib.dump(value, fp, compress=3)
    except Exception as exc:
        logger.warning(f"disk_cache save 실패 {fp.name}: {exc}")
