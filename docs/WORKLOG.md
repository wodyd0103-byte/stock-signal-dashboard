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

## [T04] digest 수집 레이어
- 일시: 2026-08-25 00:03
- 상태: 완료
- 목적: 서버 없이 관심종목·보유종목을 분석해 자료구조로 만든다. 출력은 T05.
- 변경:
  - `backend/tools/__init__.py`, `backend/tools/digest/__init__.py` (신규)
  - `backend/tools/digest/collector.py` (신규)
  - `backend/tests/test_digest_collector.py` (신규, 6 케이스)
- 검증:
  - `pytest -q` → **146 passed** (51s). 신규 6건 포함, 기존 140건 회귀 없음.
  - 실 DB `load_targets()` → 0건 (관심종목·보유종목 둘 다 비어 있음). 그래서 임시 DB에 005930(관심), 000660(보유 3주 @150,000)을 넣고 네트워크 포함 스모크 1회: **10.3초, rows=2, failures=0**. 시장심리 35(공포)까지 채워짐. pnl 계산도 보유 종목에만 붙는 것 확인.
- 결정:
  - **DB는 읽기만 한다.** digest는 앱과 같은 SQLite 파일을 열지만 아무것도 쓰지 않는다. `get_analysis`가 하는 회고 기록(`_retro_service.record`)은 라우터에 남겨뒀으므로 CLI 경로로는 실행되지 않는다 — 아침에 리포트를 뽑는 행위가 추천 이력을 오염시키면 안 된다.
  - 병렬 처리는 `market_router._buy_signals_payload`의 패턴을 그대로 따랐다 (`wait(timeout=...)` → 완료분 수집 → 미완료분 `cancel()` 후 실패 처리 → `shutdown(wait=False, cancel_futures=True)`). 일부 종목이 죽어도 나머지는 살아남는다.
  - 워커/타임아웃은 `core/config.py`의 `Settings`가 아니라 **툴 모듈에서 env로 읽는다** (`DIGEST_MAX_WORKERS`=4, `DIGEST_ITEM_TIMEOUT_SECONDS`=40). `Settings`는 서버 런타임 설정이라 CLI 전용 값을 섞지 않았다. `analyze()`는 외부 fetch 7종을 병렬로 타서 buy-signals의 경량 분석보다 무겁기 때문에 기본값도 더 넉넉하게 잡았다.
  - 같은 티커가 관심종목과 보유 양쪽에 있으면 한 줄로 합치고 `sources`에 둘 다 남긴다. 두 번 분석하면 시간이 두 배다.
  - 정렬은 신호 강도 → `final_buy_score` 내림차순 → 리스크 오름차순. 아침에 위에서부터 읽으면 되는 순서.
- **작성 중 자체 발견 버그 1건**: 시장심리를 `getattr(row, "_sentiment", None)`으로 긁는 코드를 넣었는데 `Row`에 그런 필드가 없어 항상 `None`이었다. `analysis_service.market_sentiment_dict()`를 한 번 부르는 방식으로 교체했다 — 이미 `analyze()`가 캐시를 채워둬서 캐시 히트이고, 전 종목이 실패해도 헤더에 시장 상황은 남는다.
- **모듈명 변경**: `collect.py`로 만들었다가 `collector.py`로 바꿨다. `tools/digest/__init__.py`가 함수 `collect`를 re-export하면서 동명의 서브모듈을 가려 `tools.digest.collect`가 함수로 해석됐고, 테스트가 `AttributeError: <function collect> has no attribute 'SessionLocal'`로 죽었다.
- 다음: T05 render — 터미널 표 / 마크다운 / HTML 출력과 전일 대비 신호 변경 diff.

## [T05] 스냅샷·비교·출력
- 일시: 2026-08-25 00:07
- 상태: 완료
- 목적: 수집 결과를 사람이 읽는 형태로 만들고, 직전 실행 대비 신호 변화를 뽑는다.
- 변경:
  - `backend/tools/digest/store.py` (신규, 스냅샷 저장/로드/비교)
  - `backend/tools/digest/render.py` (신규, 터미널/마크다운/HTML)
  - `backend/tests/test_digest_render.py` (신규, 15 케이스)
- 검증: `pytest tests/test_digest_render.py -q` → **15 passed**.
- 결정:
  - **"어제 파일"을 고정으로 찾지 않는다.** `load_previous()`는 오늘보다 앞선 스냅샷 중 가장 최근 것을 고른다. 주말이나 며칠 걸렀을 때 "어제"를 찾으면 비교가 통째로 사라진다. 마지막으로 돌린 날과 비교해야 변화가 이어진다.
  - 비교 결과는 **바뀐 종목만** 남긴다. 전체를 다시 보여주면 변화가 묻힌다. 정렬은 상승 전환 → 신규 → 하락 전환.
  - 손상된 스냅샷은 예외를 올리지 않고 `None`을 돌려준다. 어제 파일이 깨졌다고 오늘 리포트가 죽으면 안 된다.
  - 터미널 정렬에 `unicodedata.east_asian_width`를 쓴다. `len()`으로 폭을 재면 한글 종목명에서 표가 어긋난다. 테스트가 ANSI를 걷어낸 표시 폭이 행마다 같은지 검사한다.
  - HTML은 외부 리소스 없이 단독으로 열린다. `prefers-color-scheme`로 다크 모드까지 대응. 실패 메시지는 `html.escape` — 오류 문자열에 외부 출처(종목명·provider 응답)가 섞여 들어온다.
- 다음: T06 CLI 진입점과 `digest.bat`.

## [T06] CLI 진입점과 원클릭 실행
- 일시: 2026-08-25 00:12
- 상태: 완료
- 목적: 실제로 돌려볼 수 있는 상태로 마무리한다.
- 변경:
  - `backend/tools/digest/__main__.py` (신규)
  - `backend/tests/test_digest_cli.py` (신규, 7 케이스)
  - `digest.bat` (신규)
  - `README.md` (CLI 섹션, 저장소 구조)
  - `.gitignore` (`backend/data/digest/`)
- 검증:
  - `pytest -q` → **168 passed** (33s). 누적 회귀 없음 (140 → 146 → 168).
  - 실제 실행 2회. `DATABASE_URL`로 임시 DB를 물리고 005930(관심) + 000660(보유 3주 @150,000)을 넣어 네트워크 포함으로 돌렸다. 표·마크다운·HTML·스냅샷 4개 산출물 생성 확인.
  - 비교 경로도 실제로 확인했다. 스냅샷의 신호를 `BUY`로 고쳐 전일 파일로 심어두고 재실행 → `신호 변화 ● SK하이닉스 (000660) BUY → HOLD`가 상단에 찍혔다.
- 결정:
  - 색상은 tty가 아니면 자동으로 뺀다(`--colour auto`). 파일로 리다이렉트하거나 파이프로 넘길 때 제어문자가 섞이면 못 읽는다. `NO_COLOR` 환경변수도 존중한다.
  - Windows 콘솔은 `SetConsoleMode`로 ANSI를 켠다. 실패해도 색만 빠지고 동작은 같게 감쌌다.
  - **전 종목이 실패하면 종료코드 1.** 작업 스케줄러에 걸었을 때 조용히 넘어가면 며칠째 안 도는 걸 모른다. 일부 실패는 0 — 나머지 결과는 여전히 쓸모 있다.
  - 출력 디렉터리를 `.gitignore`에 넣었다. 보유 수량과 평단가가 들어가는 개인 정보다.
- **오늘 작업 종료 지점.** T00~T06 완료, 브랜치 `feat/watchlist-digest`, 커밋 6개.

## [T07] 브랜치 공개와 PR
- 일시: 2026-08-25 00:26
- 상태: 완료
- 목적: 오늘 작업을 원격에 올리고 리뷰 가능한 형태로 남긴다.
- 변경: 커밋 내용 변경 없음 (푸시와 PR 생성)
- 검증: PR [#36](https://github.com/wodyd0103-byte/stock-signal-dashboard/pull/36) — 파일 24개, +1782/-267, 커밋 6개. CI **backend (pytest) pass 53s**, **frontend (format/lint/unit/build/e2e) pass 1m40s**.
- 결정:
  - 푸시 직전에 첫 커밋 제목이 `@ docs: ...`로 깨져 있는 것을 발견했다. PowerShell here-string(`-m @'...'@`)을 커밋 메시지로 넘기면서 `@`가 제목에 섞여 들어갔다. 아직 푸시 전이라 `8491788`에서 새 브랜치를 따 cherry-pick으로 재생성하고 첫 커밋만 메시지를 고쳤다. `git diff --stat` 로 재생성 전후 트리가 동일한 것을 확인한 뒤 브랜치를 옮겼다. 원본은 `backup/pre-msg-fix`에 로컬로 남아 있다.
  - T05와 T06이 `git add -A` 때문에 한 커밋에 들어갔다. Task마다 커밋 규칙에 어긋나 `git reset --soft HEAD~1` 후 둘로 나눴다.
  - 커밋 메시지는 여러 줄일 때 `git commit -F -`에 heredoc으로 넘긴다. `-m @'...'@` 는 쓰지 않는다.

## 남은 작업 (다음 세션)
- **T07** 작업 스케줄러 등록 안내 — `schtasks` 명령과 확인 절차. 등록 자체는 사용자가 직접.
- **T08** 알림 — 신호 변화가 있을 때만 Windows 토스트 또는 메일. 변화 없는 날 알림이 오면 곧 무시하게 된다.
- **T09** 신호 변화 이력을 별도 테이블로. 지금은 JSON 스냅샷 비교라 "지난달에 몇 번 뒤집혔나"를 못 본다. `retrospective_service`가 먹을 수 있는 형태가 되면 리서치 탭과 연결된다.
- **부채(T03에서 발견, 범위 밖)**: `scheduler_service`가 `market_router._buy_signals_payload`와 `surge_router.scan_surge`를 import한다. `market_router`는 `StockDataProvider()`를 자체 생성해 `analysis_service`와 인스턴스가 갈린다.
