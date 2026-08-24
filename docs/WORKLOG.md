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
