# 작업 로그 (WORKLOG)

Watchlist Daily Digest 미니툴 개발 기록. Task 하나가 끝날 때마다 아래에 엔트리를 하나씩 append 한다. 엔트리는 지우지 않고 상태만 갱신한다.

## 엔트리 형식

```
## [Txx] 제목
- 일시: YYYY-MM-DD HH:MM
- 상태: 계획 / 진행중 / 완료 / 보류 / 폐기
- 목적: 왜 이 작업을 하는지 한 줄
- 변경: 건드린 파일 목록 (없으면 "없음 (조사만)")
- 검증: 실행한 명령과 결과. 검증 안 했으면 "미검증"이라고 그대로 적는다
- 결정: 갈림길에서 무엇을 골랐고 왜인지
- 다음: 바로 이어지는 작업
```

규칙
- 검증하지 않은 것을 "완료"로 적지 않는다. 테스트가 깨졌으면 깨진 그대로 적는다.
- 작업 도중 방향을 바꾸면 원래 엔트리를 수정하지 말고 새 엔트리에 사유를 남긴다.

---

## [T00] 미니툴 기획 및 코드베이스 조사
- 일시: 2026-08-24 23:35
- 상태: 완료
- 목적: 기존 QUANT 코드를 재사용하는 가벼운 부속 툴 후보를 정한다.
- 변경: 없음 (조사만)
- 검증: `backend/app` 구조, `requirements.txt`, `WatchlistItem` 모델, `SignalService` 메서드, `stock_router` 엔드포인트 확인. git 상태 clean, branch=main, remote=origin(stock-signal-dashboard).
- 결정: **Watchlist Daily Digest** (헤드리스 CLI)로 확정. 서버/프론트 없이 관심종목+보유종목 신호를 터미널 표와 md/html 파일로 출력. 새 의존성 0개, 기존 service 레이어 재사용이 핵심이라 진입 비용이 가장 낮음.
- 다음: T01 작업 로그 인프라 구축.

## [T01] 작업 로그 인프라 구축
- 일시: 2026-08-24 23:41
- 상태: 완료
- 목적: 이후 모든 작업을 Task 단위로 추적한다.
- 변경: `docs/WORKLOG.md` (신규)
- 검증: 파일 생성 확인.
- 결정: 별도 도구 없이 마크다운 단일 파일. 기존 `docs/ARCHITECTURE.md`, `docs/RETROSPECTIVE.md`와 같은 위치에 둬서 문서가 한곳에 모이게 함. 브랜치 `feat/watchlist-digest`를 파고 Task마다 커밋한다.
- 다음: T02 분석 파이프라인을 `stock_router`에서 service 레이어로 추출 (Phase 0).

## [T02] 분석 파이프라인을 analysis_service로 추출
- 일시: 2026-08-24 23:52
- 상태: 완료
- 목적: CLI가 FastAPI 없이 분석 파이프라인을 직접 호출할 수 있게 한다.
- 변경:
  - `backend/app/services/analysis_service.py` (신규)
  - `backend/app/routers/stock_router.py` (수정, -227/+82)
  - `backend/tests/test_routers.py` (수정, 스텁 대상 이동)
- 검증: `.venv/Scripts/python.exe -m pytest -q` → **140 passed** (57s). 서비스 모듈 단독 import 성공, fastapi import 0건 확인.
- 결정:
  - **조사 결과 `stock_router`는 이미 사실상 공용 서비스 허브였다.** export/watchlist/market/portfolio/ic/retrospective 라우터와 `scheduler_service`까지 7곳이 `_load_enriched`, `_build_signal`, `_quote_from_frame`, 싱글턴 등을 private 이름으로 import하고 있었다. 추출 이득이 digest 하나에 그치지 않는다.
  - 한 번에 옮기면 호출부 7곳이 동시에 깨진다. **T02는 서비스 신설 + 라우터가 옛 이름을 별칭으로 재export** 해서 무중단으로 두고, 호출부 이전은 T03으로 분리했다.
  - HTTP 예외를 서비스에 두면 CLI에서 `HTTPException`을 잡아야 한다. 서비스는 `DataProviderError` / 신설 `AnalysisError`만 올리고, 라우터의 `_http_error()`가 상태코드로 변환한다. 기존 매핑(invalid_ticker_format→400, 그 외 provider 오류→502, 지표 실패→500)과 메시지는 그대로 유지.
  - 서비스를 클래스가 아닌 **모듈 함수**로 뒀다. 다른 서비스들은 클래스지만, 이 모듈은 조합 레이어이고 테스트가 `monkeypatch.setattr(module, name, ...)`로 외부 fetch를 끄는 구조라 모듈 함수가 스텁하기 쉽다.
  - `analyze()`는 `AnalysisBundle` 데이터클래스를 돌려준다. 라우터는 이걸 `AnalysisResponse`로, CLI는 표/리포트로 변환한다. 응답 스키마와 회고 기록(`_retro_service.record`, db 세션 필요)은 라우터에 남겼다.
  - `_price_points`, `_optional_float`은 응답 스키마(`PricePoint`) 전용이라 라우터에 남겼다.
  - conftest는 `analysis_service`와 `stock_router` 별칭 **양쪽**을 스텁한다. `market_router`가 함수 안에서 `from app.routers.stock_router import _fundamental_dict`로 별칭을 직접 집어가기 때문에 한쪽만 막으면 테스트가 실제 네트워크를 탄다.
- 다음: T03 호출부 7곳을 `analysis_service` 직접 import로 이전하고 별칭 제거.

## [T03] 호출부 7곳 이전 및 별칭 제거
- 일시: 2026-08-25 00:14
- 상태: 완료
- 목적: `stock_router`를 공용 허브에서 다시 라우터로 되돌린다.
- 변경:
  - `backend/app/routers/analysis_http.py` (신규, HTTP 어댑터)
  - `backend/app/routers/stock_router.py` (별칭 21개 + 로컬 래퍼 제거)
  - `backend/app/routers/{export,watchlist,market,portfolio,ic,retrospective}_router.py`
  - `backend/app/services/scheduler_service.py`
  - `backend/tests/test_routers.py` (스텁 대상 정리)
- 검증: `pytest -q` → **140 passed** (48s). `app.main` import 성공, OpenAPI 28 path 생성. AST 스캔으로 `app/services/*`가 `app.routers`를 import하는지 확인.
- 결정:
  - HTTP 매핑을 `stock_router`에 두면 다른 라우터가 또 stock_router를 import하게 된다. **`app/routers/analysis_http.py`로 분리**해서 `to_http_exception`, `load_enriched`, `analyze`를 제공한다. 이제 아무도 `stock_router`의 내부를 import하지 않는다 (`main.py`의 라우터 등록만 남음).
  - 호출부를 **두 부류로 갈랐다.** 실패를 그대로 4xx/5xx로 올려야 하는 쪽(`stock_router` 전 엔드포인트, `export_stock_analysis`)은 `analysis_http`를, 실패를 응답 안에 담고 계속 가는 쪽(`list_watchlist`, `export_watchlist`의 행별 error 컬럼, `scheduler_service` 캐시 워밍)은 `analysis_service`를 직접 부른다. 후자는 원래 `HTTPException`을 `except Exception`으로 받아 문자열화하고 있었다 — 서비스 예외를 그대로 받는 게 맞다.
- **동작 변화 1건 (의도됨)**: 관심종목 목록과 watchlist CSV의 `error` 필드에서 `"500: "` / `"502: "` 접두사가 사라진다. `str(HTTPException)`이 `f"{status_code}: {detail}"`을 돌려주던 것이 도메인 예외 메시지로 바뀌었기 때문. 응답 스키마와 상태코드는 불변이고, 해당 테스트는 error가 truthy인지만 본다. CSV/화면에는 오히려 읽기 좋아진다.
- 남은 레이어링 부채 (이번 범위 밖, 기존 이슈):
  - `scheduler_service`가 여전히 `market_router._buy_signals_payload`와 `surge_router.scan_surge`를 import한다. 캐시 워밍이 라우터 레벨 payload 빌더에 묶여 있어서인데, 별도 작업으로 다뤄야 한다.
  - `market_router`는 `StockDataProvider()` 등 싱글턴을 자체 생성해 `analysis_service`와 인스턴스가 갈린다. 캐시가 이중으로 뜨지만 동작상 문제는 없어 그대로 뒀다.
- 다음: T04 digest collect — 관심종목/보유종목 티커 수집 후 `analysis_service.analyze()` 병렬 실행.
