"""분석 서비스의 도메인 예외를 HTTP 응답으로 바꾸는 어댑터.

`app/services/analysis_service.py`는 HTTP를 모른다. 요청 컨텍스트에서 그 함수들을
부르는 라우터는 이 모듈을 거쳐 상태코드 변환을 얻는다. 실패를 응답 본문에 담아
계속 진행하는 쪽(관심종목 목록, CSV 행별 error 컬럼)은 서비스를 직접 부르고
예외를 스스로 처리한다.
"""
from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from app.services import analysis_service
from app.services.analysis_service import AnalysisBundle, AnalysisError
from app.services.data_provider import DataProviderError, PriceDataResult


def to_http_exception(exc: Exception, ticker: str) -> HTTPException:
    """형식 오류는 사용자 잘못이라 400, 업스트림 실패는 502, 그 외 처리 실패는 500."""
    if isinstance(exc, DataProviderError):
        status_code = 400 if exc.error_type == "invalid_ticker_format" else 502
        return HTTPException(status_code=status_code, detail=exc.to_payload(ticker))
    return HTTPException(status_code=500, detail=str(exc))


def load_price_data_result(ticker: str, period: str) -> PriceDataResult:
    try:
        return analysis_service.load_price_data_result(ticker, period)
    except DataProviderError as exc:
        raise to_http_exception(exc, ticker) from exc


def load_enriched(ticker: str, period: str) -> tuple[PriceDataResult, pd.DataFrame]:
    try:
        return analysis_service.load_enriched(ticker, period)
    except (DataProviderError, AnalysisError) as exc:
        raise to_http_exception(exc, ticker) from exc


def analyze(ticker: str, period: str) -> AnalysisBundle:
    try:
        return analysis_service.analyze(ticker, period)
    except (DataProviderError, AnalysisError) as exc:
        raise to_http_exception(exc, ticker) from exc
