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

## [T08] 종목 등록 CLI
- 일시: 2026-08-25 00:47
- 상태: 완료
- 목적: digest를 실제로 쓸 수 있게 한다. 관심종목·보유가 0건이라 지금은 빈 표만 나온다.
- 변경:
  - `backend/tools/stocks/__init__.py`, `registry.py`, `__main__.py` (신규)
  - `backend/tests/test_stocks_cli.py` (신규, 13 케이스)
- 검증: `pytest tests/test_stocks_cli.py -q` → **13 passed**. 실 DB에 `python -m tools.stocks list` 실행 → 관심종목 0건 / 보유 0건 정상 출력 (읽기만).
- 결정:
  - **동작을 REST 엔드포인트와 맞췄다.** 관심종목 추가는 멱등(이미 있으면 그대로), 보유 추가는 재매수 평균으로 합친다. 두 경로가 다르게 굴면 CLI로 넣은 종목과 화면으로 넣은 종목이 서로 다른 상태가 된다. 덮어쓰려면 `--replace`를 따로 줘야 한다.
  - 티커 대신 **종목명도 받는다** (`watch add 삼성전자`). `app/core/stock_universe.py`의 대표 목록으로 이름↔티커를 양방향 조회하고, 목록에 없으면 `resolve_ticker`로 넘긴다. 대표 목록은 편의용이지 허용 목록이 아니라서, 목록 밖 종목도 그대로 통과시킨다.
  - 종료코드를 나눴다: 없는 종목 삭제 1, 잘못된 입력(티커 형식 오류·수량 0 이하) 2. 스크립트에서 구분해 처리할 수 있다.
  - 등록 로직은 `registry.py`에 Session을 받는 순수 함수로 두고 CLI는 얇게. 테스트가 CLI를 거치지 않고도 로직을 부를 수 있다.
- 다음: T09 신호 변화 이력 테이블.

## [T09] 신호 변화 이력 테이블
- 일시: 2026-08-25 01:05
- 상태: 완료
- 목적: "이 종목이 최근 몇 번 뒤집혔나"에 답할 수 있게 한다. JSON 스냅샷은 직전 대비만 답한다.
- 변경:
  - `backend/app/models/signal_change.py` (신규)
  - `backend/migrations/versions/0004_signal_changes.py` (신규)
  - `backend/app/database.py` (`init_db`에 모델 등록)
  - `backend/tools/digest/history.py` (신규), `backend/tools/digest/__main__.py` (기록 배선)
  - `backend/tests/test_digest_history.py` (신규, 7 케이스), `backend/tests/test_digest_cli.py` (DB 격리 + 이력 검증)
- 검증:
  - `pytest -q` → **188 passed** (79s). 168 → 188 (+13 T08, +7 T09).
  - 실 DB 마이그레이션 적용. 적용 전 `quant_app.db`를 스크래치패드에 백업(`quant_app.db.bak-20260825-220240`).
  - `alembic downgrade -1` → `upgrade head` 왕복 확인. 최종 리비전 `0004_signal_changes`, 인덱스 3개 생성 확인.
- **T04 결정 일부 변경**: T04에서 "digest는 DB를 읽기만 한다"고 정했다. 그 규칙의 목적은 **추천 이력(회고 데이터) 오염 방지**였고 그건 그대로다 — digest는 지금도 `recommendations`를 건드리지 않는다. `signal_changes`는 digest가 스스로 만드는 자기 기록이라 성격이 다르다고 판단해 쓰기를 허용했다. `--no-save`를 주면 스냅샷과 함께 이력 기록도 건너뛴다.
- 결정:
  - **같은 날 같은 전환은 한 번만 적재한다.** 하루에 digest를 두 번 돌린다고 이력이 부풀면 "몇 번 뒤집혔나"가 실행 횟수를 세는 지표가 된다.
  - 변화가 있는데 그 종목이 이번 실행에서 실패해 `rows`에 없을 수 있다. 그 경우 가격·점수를 `None`으로 두고 변화 자체는 남긴다.
  - `flip_counts()`를 같이 넣었다. 자주 뒤집히는 종목일수록 신호를 덜 믿어야 한다는 판단 재료이고, 나중에 `retrospective_service`가 읽을 자리다.
- **잡은 버그 2건**:
  - 마이그레이션이 `index ix_signal_changes_id already exists`로 죽었다. 컬럼 정의의 `primary_key=True, index=True`가 이미 인덱스를 만드는데 `op.create_index`로 또 만들었다. 테이블만 생기고 리비전은 0003에 멈춘 반쯤 적용된 상태가 됐다. 빈 테이블(0행)임을 확인하고 drop 후 재적용했다.
  - `test_digest_cli.py`가 `SessionLocal`을 패치하지 않아 **테스트가 실제 앱 DB에 접근**했다. 임시 DB로 격리했다. 하위 디렉터리에 두지 않으면 산출물 목록 검사에 DB 파일이 섞인다.
- 다음: T10 변화가 있을 때만 알림.

## [T10] 신호 변화 알림
- 일시: 2026-08-25 01:24
- 상태: 완료
- 목적: 매일 리포트를 열어보지 않아도 바뀐 것만 눈에 들어오게 한다.
- 변경:
  - `backend/tools/digest/notify.py` (신규)
  - `backend/tools/digest/__main__.py` (`--notify` 플래그)
  - `backend/tests/test_digest_notify.py` (신규, 13 케이스)
  - `README.md`, `digest.bat` (`--notify` 추가)
- 검증:
  - `pytest -q` → **201 passed** (54s). 188 → 201.
  - **실제 토스트 1회 발사 확인**: `backend=toast`, fallback 안 탐. 화면에 알림 표시됨.
- 결정:
  - **변화가 있을 때만 보낸다.** 변화 없는 날에도 알림이 오면 며칠 만에 무시하게 되고, 그때부터 알림은 없는 것과 같다. 이건 옵션이 아니라 기본 동작으로 박았다.
  - **외부 패키지를 안 쓴다.** BurntToast 같은 모듈을 요구하면 스케줄러에 걸어둔 뒤 환경이 바뀌었을 때 조용히 죽는다. PowerShell로 WinRT `ToastNotificationManager`를 직접 부르고, AUMID는 PowerShell 자체 것을 쓴다(별도 앱 등록 불필요).
  - **XML을 base64로 넘긴다.** 종목명·신호는 외부 데이터고 따옴표나 꺾쇠가 섞일 수 있다. 명령줄에 직접 끼우면 PowerShell 인용 규칙을 타고 깨지거나 주입 통로가 된다. base64 문자셋은 `[A-Za-z0-9+/=]`뿐이라 작은따옴표 안에서 안전하다. XML 안의 값은 `xml.sax.saxutils.escape`로 한 번 더 막는다. 테스트가 종목명이 스크립트 문자열에 **직접 나타나지 않는지**까지 검사한다.
  - `--notify` 기본값은 `off`. 자동으로 알림을 켜지 않는다. `auto`는 토스트 실패 시 콘솔로 떨어지고, `toast`는 떨어지지 않는다(스케줄러에서 실패를 조용히 덮지 않으려는 경우).
  - 토스트 실패는 예외로 올리지 않는다. 알림이 안 떴다고 리포트 생성이 실패하면 안 된다.
- 다음: T11 작업 스케줄러 등록 안내.

## [T11] 작업 스케줄러 등록 안내
- 일시: 2026-08-25 01:38
- 상태: 완료
- 목적: 아침마다 자동 실행할 수 있게 절차를 남긴다. **등록 자체는 사용자가 직접** — 시스템 설정 변경이다.
- 변경:
  - `docs/SCHEDULING.md` (신규)
  - `digest-scheduled.bat` (신규)
  - `start.bat`, `stop.bat`, `digest-scheduled.bat` (워킹트리 줄바꿈 CRLF로 교정)
  - `README.md` (스케줄링 문서 링크, 저장소 구조)
- 검증: `digest-scheduled.bat`을 PowerShell에서 실제 실행 → 종료코드 0, `.md`/`.html`/`.json` 3개 생성 확인.
- 결정:
  - **배치 파일을 둘로 나눴다.** `digest.bat`은 사람용(브라우저 열기 + 실패 시 `pause`), `digest-scheduled.bat`은 자동 실행용(둘 다 없음). 자동 실행에 사람용을 걸면 자리에 없을 때 브라우저가 뜨고, 실패 시 `pause`가 걸려 작업이 끝나지 않은 채로 남는다.
  - `schtasks` 명령은 문서에 적기만 하고 실행하지 않았다. 등록·해제·확인·실패 코드 해석까지 적어 뒀다.
  - 종료코드에 9를 추가했다(가상환경 없음). 스케줄러의 `Last Result`만 보고 원인을 구분할 수 있다.
- **잡은 버그 1건**: `digest-scheduled.bat`을 실제로 돌리자 `'…' is not recognized`가 떴다. 원인은 줄바꿈 — cmd.exe는 CRLF를 요구하는데 LF로 저장돼 있었고, 한글 `REM`이 섞인 줄에서 파싱이 깨졌다. `start.bat`, `stop.bat`도 워킹트리가 같은 상태였다. 셋 다 CRLF로 고쳤다. 실행해 보지 않았으면 못 잡았을 버그다.
  - 저장소에는 이미 `.gitattributes`에 `*.bat text eol=crlf` 규칙이 있었다. 이 속성은 **체크아웃할 때** 적용되므로, 내가 도구로 직접 쓴 파일에는 걸리지 않아 LF로 남았던 것이다. `git add --renormalize`로 정리했다 — 워킹트리는 CRLF, 저장소에는 LF로 들어간다.
- **내가 낸 사고 1건**: 위 규칙이 이미 있는 줄 모르고 `.gitattributes`를 **새로 쓰면서 기존 내용을 덮어썼다.** 원본에 있던 `* text=auto eol=lf`가 사라졌는데, 이건 Windows 체크아웃에서 워킹트리가 CRLF가 되어 `npm run format:check`가 로컬에서만 깨지는 것을 막는 규칙이다. `git show HEAD~1:.gitattributes`로 원복했다. 파일을 새로 만들기 전에 존재 여부를 먼저 확인해야 했다.
- 다음: T12 문서 정리 후 PR.

## [T12] 유니버스 스캔을 서비스로 추출
- 일시: 2026-08-25 02:15
- 상태: 완료
- 목적: `scheduler_service`가 라우터를 import하지 않게 한다. 캐시 워밍이 라우터 레벨 payload 빌더에 묶여 있었다.
- 변경:
  - `backend/app/services/scan_service.py` (신규, 338줄)
  - `backend/app/routers/market_router.py` (440줄 → **129줄**)
  - `backend/app/routers/export_router.py`, `backend/app/services/scheduler_service.py` (호출부 이전)
  - `backend/tests/test_routers.py` (캐시 초기화 대상 이전, 낡은 주석 수정)
- 검증: `pytest -q` → **201 passed** (58s). 회귀 없음. AST 스캔으로 `app/services/*`의 라우터 import 확인 → `scheduler_service` → `surge_router` 하나만 남음(T13 대상).
- 결정:
  - **싱글턴을 새로 만들지 않고 `analysis_service`의 것을 가져다 썼다.** `market_router`는 `StockDataProvider` 등 10개를 자체 생성해 `analysis_service`와 인스턴스가 갈려 있었고, provider 캐시가 두 벌로 떴다. 추출하면서 공유로 바꿨으니 원래 T13에 있던 "싱글턴 통합"의 절반이 여기서 끝났다. `StockDataProvider()` 생성 위치는 4곳 → **2곳**(`analysis_service`, `surge_router`)으로 줄었다.
  - 중복 정의였던 `_return_pct`, `_liquidity_score`는 `analysis_service`의 것으로 통일했다. `_liquidity_score`는 빈 DataFrame일 때만 결과가 달랐는데(`analysis_service`는 0.0, `market_router`는 70.0), 스캔 경로는 그 앞에서 `len(enriched) < 2`로 걸러내므로 도달 불가능한 차이다.
  - `prediction_service = PredictionService()`는 `market_router`에서 만들기만 하고 아무도 쓰지 않는 죽은 코드였다. 지웠다.
  - 캐시 초기화용 `clear_caches()`를 서비스에 뒀다. 테스트가 모듈 내부 dict를 직접 만지던 것을 함수 하나로 바꿨다.
  - `compare` 엔드포인트는 라우터에 남겼다. 유니버스 스캔이 아니라 별개 기능이고, 필요한 헬퍼는 `analysis_service`에서 가져온다.
- 다음: T13 `surge_router.scan_surge` 추출 — 이게 끝나야 서비스가 라우터를 아는 곳이 하나도 없다.

## [T13] 급등 스캔을 서비스로 추출
- 일시: 2026-08-25 02:34
- 상태: 완료
- 목적: `scheduler_service`의 마지막 라우터 의존을 끊는다.
- 변경:
  - `backend/app/services/surge_scan_service.py` (신규)
  - `backend/app/routers/surge_router.py` (200줄 → **66줄**)
  - `backend/app/services/scheduler_service.py`, `backend/tests/test_routers.py` (호출부·캐시 초기화 이전)
- 검증:
  - `pytest -q` → **201 passed** (60s). 회귀 없음.
  - AST 스캔: `app/services/*` → `app.routers` import **0건**. 목표 달성.
  - `StockDataProvider()` 생성 위치 **1곳**(`analysis_service`). 시작 시점엔 4곳이었다.
  - `app.main` import 성공, 라우트 34개 · OpenAPI 28 path — 추출 전과 동일.
- 결정:
  - 스캔 로직이 **엔드포인트 함수 본문에 통째로 들어 있었다.** `Query(...)` 기본값이 곧 함수 시그니처라 스케줄러가 라우터 함수를 직접 부르는 구조였다. 서비스의 `scan()`은 같은 인자 이름을 평범한 기본값으로 받고, `Query` 제약(ge/le)은 라우터에 남겼다 — 범위 검증은 HTTP 입력에 필요한 것이지 내부 호출자에게 강요할 것이 아니다.
  - 서비스가 `SurgeItem` 스키마로 항목을 정규화해 dict를 돌려주고, 라우터가 `SurgeScanResponse`로 감싼다. `analysis_service`가 `AnalysisBundle`을 돌려주고 라우터가 응답 스키마를 만드는 것과 같은 모양.
  - 단일 종목 예측도 `predict_one()`으로 뺐다. 라우터가 `RuntimeError`를 400으로 옮긴다.
  - 유니버스 싱글턴은 `scan_service`의 것을 공유한다. 따로 만들면 유니버스 캐시가 두 벌이 된다.
- **정리 결과 (T02부터 T13까지)**: 시작할 때 `stock_router`는 다른 모듈 7곳이 private 헬퍼를 가져다 쓰는 사실상의 서비스 허브였고, 라우터 3개가 provider 싱글턴을 각자 만들고 있었다. 지금은 서비스가 라우터를 모르고, provider는 한 인스턴스이며, `market_router` 440→129줄 · `surge_router` 200→66줄로 줄었다.

## [T14] 리포트에 전환 횟수 붙이기
- 일시: 2026-08-25 03:02
- 상태: 완료
- 목적: 오늘의 변화를 얼마나 믿을지를 같은 화면에서 판단하게 한다.
- 변경:
  - `backend/tools/digest/render.py` (세 렌더러에 `flips` 인자, `_flip_note`)
  - `backend/tools/digest/__main__.py` (실행 순서 재배치)
  - `backend/tests/test_digest_render.py` (+4), `backend/tests/test_digest_cli.py` (+2)
  - `README.md`
- 검증:
  - `pytest -q` → **207 passed** (46s). 201 → 207.
  - 임시 DB에 과거 전환 2건을 심고 네트워크 포함으로 2회 실행. 터미널 `BUY → HOLD · 30일 3회`, 마크다운 `— BUY → HOLD _(30일 3회)_` 확인. 심어둔 2건 + 오늘 1건이 맞다.
- 결정:
  - **이력 적재를 렌더링보다 먼저로 옮겼다.** 원래는 렌더 → 저장 → 기록 순서였는데, 그대로 두면 오늘의 전환이 빠진 숫자가 리포트에 찍힌다. "오늘 뒤집혔고 30일에 2회"와 "3회" 중 맞는 것은 3회다. `--no-save`면 기록을 건너뛰므로 그만큼 숫자가 낮게 나오는데, 애초에 아무것도 남기지 않겠다는 옵션이라 그대로 뒀다.
  - **2회 미만은 표시하지 않는다.** 1회는 방금 그 전환 자체라서 셀 것이 없다. "30일 1회"가 붙으면 정보가 아니라 잡음이다.
  - DB 세션을 한 번만 연다. 기록과 조회가 같은 세션을 쓴다.
  - 창 길이(30일)는 `render.HISTORY_WINDOW_DAYS` 한 곳에 두고 CLI가 그 값으로 조회한다. 표시 문구와 조회 범위가 갈리면 숫자가 거짓말을 한다.
- 다음: 남은 것은 아래 목록. 코드 쪽은 리서치 탭 연결과 메일 알림.

## [T15] 신호 이력을 리서치 탭에
- 일시: 2026-08-25 03:26
- 상태: 완료
- 목적: digest가 쌓은 전환 이력을 화면에서도 본다. 지금까지는 CLI 출력에만 있었다.
- 변경:
  - 백엔드: `app/services/signal_history_service.py` (신규), `app/routers/retrospective_router.py` (`GET /retrospective/signal-changes`), `tools/digest/history.py` (어댑터로 축소), `tests/test_signal_history_service.py` (신규 6), `tests/test_routers.py` (+3)
  - 프론트: `components/SignalHistoryPanel.tsx` + 테스트 6, `lib/types.ts`, `lib/api.ts`, `hooks/queries.ts`, `app/page.tsx`, `demo-data/signal-changes.json`, `scripts/build-demo-api.mjs`, `tests/mock-api.ts`, `tests/demo-api.spec.ts`, `tests/signal-history.spec.ts` (신규 3)
- 검증:
  - 백엔드 `pytest -q` → **217 passed**.
  - 프론트 `format:check` · `lint` 통과, `vitest` **159 passed**, `next build` 타입체크 통과, `playwright` **51 passed**.
  - 브라우저에서 실제 확인: 백엔드·프론트 dev 서버를 띄워 리서치 탭에 패널이 회고와 IC 사이에 붙는 것과 엔드포인트가 `{"days":30,"total":0,...}`를 돌려주는 것을 확인.
- 결정:
  - **적재·조회 로직을 `app/services/`로 옮겼다.** 화면이 읽으려면 API가 필요한데, 라우터가 `tools/digest/history.py`를 import하면 앱이 CLI 도구에 의존하게 된다. 서비스는 `Digest`·`Change` 같은 CLI 자료구조를 모르고 평범한 dict를 받는다. 변환은 `tools/digest/history.py`가 맡아 얇은 어댑터로 남았다.
  - 엔드포인트를 `retrospective` 아래에 뒀다. 리서치 탭이 이미 그 prefix를 읽고 있고, "지난 판단이 실제로 어땠나"라는 질문이 회고와 같은 종류다.
  - **패널은 접힌 채로 시작하고 펼칠 때만 조회한다.** 회고·IC 패널과 같은 방식이다. 리서치 탭을 여는 것만으로 세 종류의 조회가 동시에 나가면 안 된다.
  - 기록이 없을 때 "고장"이 아니라 "아직 없음"으로 말하고, 이력이 digest 실행으로 쌓인다는 사실과 명령까지 화면에 적었다. 이 값은 화면이 만드는 것이 아니라서, 비어 있는 이유를 모르면 버그로 보인다.
  - 데모 배포용 픽스처(`demo-data/signal-changes.json`)를 같이 넣었다. 데모에서 이 패널만 비면 링크로 들어온 사람에게는 그게 앱의 전부다.
- **주의**: `next dev`를 띄우면 `frontend/AGENTS.md`와 `frontend/CLAUDE.md`가 자동 생성된다(Next.js가 `generate-agent-files.js`로 쓴다). 이번 작업과 무관하고 저장소에 에이전트 지침을 둘지는 별도 판단이라 커밋하지 않고 지웠다. `next dev`를 돌릴 때마다 다시 생긴다.

## [T16] 메일 알림과 중복 차단
- 일시: 2026-08-25 03:52
- 상태: 완료
- 목적: 토스트는 그 PC 앞에 있어야 보인다. 그리고 같은 알림이 반복되지 않게 한다.
- 변경:
  - `backend/tools/digest/notify.py` (메일 채널, 지문 기반 중복 차단)
  - `backend/tools/digest/__main__.py` (`--notify email|all`, `--renotify`)
  - `backend/tests/test_digest_notify.py` (+12)
  - `backend/.env.example`, `README.md`, `docs/SCHEDULING.md`
- 검증:
  - `pytest -q` → **229 passed** (217 → 229).
  - 실제 실행으로 중복 차단 확인: 같은 변화로 두 번 돌려 1회차는 `[알림] 신호 변화 1건`, 2회차는 `알림: 같은 변화로 이미 알림을 보냈습니다`. 지문 파일 `.notified.json` 생성 확인.
  - **검증 중 토스트를 띄우지 않았다.** 사용자가 반복 알림을 원하지 않는다고 했으므로 `--notify console` 로 확인했다.
  - 메일은 `smtplib.SMTP`를 대역으로 갈아끼워 검사했다. 실제 메일은 한 통도 보내지 않았다.
- 결정:
  - **중복 차단을 토스트에도 걸었다.** 요청은 메일이었지만 "같은 알림이 계속 오는 게 싫다"는 문제는 채널과 무관하다. 보낸 변화 묶음의 지문(정렬한 `ticker:이전>현재` 의 sha256 앞 16자)을 출력 디렉터리에 남기고 다음 실행에서 비교한다. 순서가 달라도 같은 묶음이면 같은 지문이 나온다.
  - **발송에 실패하면 기억하지 않는다.** 실패를 기억하면 그 변화는 영영 알림이 안 간다. SMTP 설정이 비어 발송을 건너뛴 경우도 마찬가지다 — 설정을 채우면 그 변화로 알림이 온다.
  - 지문 파일이 깨져 있으면 무시하고 보낸다. 중복 한 번이 누락 한 번보다 낫다.
  - **SMTP 값 네 개가 모두 있을 때만 메일을 시도한다.** 하나라도 비면 오류가 아니라 "설정이 없다"는 안내로 끝난다. 자격증명은 사용자가 직접 `.env`에 넣는다 — 내가 입력하지 않는다.
  - `--notify` 기본값은 여전히 `off`. 알림은 명시적으로 켜야 동작한다.
- 다음: 코드로 남은 항목 없음. 나머지는 직접 해야 하는 설정.

---

# 2026-08-26

## [T17] 첫 실사용 실행
- 일시: 2026-08-26 20:57
- 상태: 완료
- 목적: 어제까지 전부 임시 DB로만 검증했다. 실 DB·실 시세로 하루치를 돌려본다.
- 변경: 없음 (실행만)
- 검증: `python -m tools.digest --md --html` → 4종목 분석, 실패 0. 어제(08-25 22:26) 스냅샷과 비교됨.
- **결과: 변화 0건으로 보고됐지만 실제로는 크게 움직였다.**

| 종목 | 신호 | 매수점수 | 리스크 |
| --- | --- | --- | --- |
| SK하이닉스 | HOLD → HOLD | 0 → 21 | 82 → 92 |
| NAVER | HOLD → HOLD | 1 → 18 | 80 → 58 |
| 카카오 | HOLD → HOLD | 16 → 10 | 82 → 70 |
| 삼성전자 | HOLD → HOLD | 2 → 9 | 78 → 78 |

- 원인: 변화 판정이 신호 등급만 봤다. 등급 경계를 넘지 않으면 점수가 0→21로 뛰어도 "변화 없음"이다. 매일 리포트를 여는 사람에게 "어제랑 똑같다"로 읽히는데 사실이 아니다.
- 다음: T18에서 판정 기준을 넓힌다.

## [T18] 점수·리스크 이동도 변화로 본다
- 일시: 2026-08-26 21:12
- 상태: 완료
- 목적: T17에서 드러난 결함. 등급이 안 바뀌어도 크게 움직였으면 말해야 한다.
- 변경:
  - `backend/tools/digest/store.py` (`Change.kind`, `diff_signals` 확장)
  - `backend/tools/digest/render.py` (종류별 문구·섹션 제목)
  - `backend/tools/digest/notify.py`, `__main__.py` (`--score-move`)
  - `backend/app/models/signal_change.py`, `migrations/versions/0005_signal_change_kind.py`
  - `backend/app/services/signal_history_service.py`, `backend/tools/digest/history.py`
  - 프론트: `lib/types.ts`, `components/SignalHistoryPanel.tsx`(+테스트), `demo-data/signal-changes.json`
  - `README.md`, `backend/.env.example`
  - 테스트 +18 (`test_digest_render.py`, `test_signal_history_service.py`, `test_digest_notify.py`)
- 검증:
  - 백엔드 `pytest -q` → **247 passed** (229 → 247).
  - 프론트 `format:check`·`lint`·`vitest 159`·`next build`·`playwright 51` 전부 통과.
  - 마이그레이션 `0005` 적용 + `downgrade -1` → `upgrade head` 왕복 확인. 실 DB 백업 후 진행.
  - **같은 데이터로 재실행해 결함 해소 확인**: T17에서 "변화 없음"이던 날이 이제 3건으로 나온다 — `SK하이닉스 매수점수 0 → 21`, `NAVER 매수점수 1 → 18`, `NAVER 리스크 높음 → 보통`. 카카오(6점)·삼성전자(7점)는 기준 미만이라 조용하다.
- 결정:
  - **세 종류를 구분해 기록한다** (`kind`: signal / score / risk). 한 덩어리로 뭉치면 "몇 번 뒤집혔나"를 셀 수 없다.
  - **등급이 바뀐 종목의 점수 이동은 생략한다.** 등급이 바뀔 정도면 점수도 당연히 움직였고, 같은 사실을 두 줄로 말하면 소음이다.
  - **전환 횟수(`flip_counts`)는 등급 전환만 센다.** 점수 이동까지 세면 그 숫자가 무슨 뜻인지 흐려진다. 화면 문구도 "등급이 바뀐 횟수만 셉니다"로 바꿨다.
  - **점수 이동에는 전환 횟수를 붙이지 않는다.** 몇 점 움직였는지 옆에 "30일 3회"가 붙으면 두 이야기가 한 줄에 섞인다.
  - **섹션 제목이 내용을 따라간다.** 점수만 움직인 날에 "신호 변화"라고 쓰면 등급이 바뀐 날과 구분이 안 된다 → `신호 변화` / `점수·리스크 이동` / `오늘 달라진 것`.
  - **알림 지문에 종류를 넣었다.** 안 넣으면 같은 종목의 등급 전환과 점수 이동이 같은 알림으로 취급돼 두 번째가 막힌다.
  - 기준값 15점은 `--score-move` / `DIGEST_SCORE_MOVE_FLOOR` 로 조정. 리스크는 점수가 아니라 등급이 바뀔 때만 — 78→92처럼 등급 안에서 움직이는 것까지 보고하면 매일 시끄럽다.
- **작업 중 잡은 것**: 데모 픽스처를 고치면서 `flips`(000660 2회)와 실제 등급 전환 행(1건)이 어긋났다. 검사를 한 종목에만 걸어서 놓쳤고, 모든 종목에 대해 규칙을 검사하도록 고쳤다.
- 다음: T19 회고 채점 살리기.

## [T19] 회고 채점 살리기 + 시점 가격으로 채점
- 일시: 2026-08-26 21:30
- 상태: 완료
- 목적: `evaluate_due()`가 도는 곳이 스케줄러(미등록)와 화면 버튼뿐이라 추천이 영영 채점되지 않았다. horizon 5일짜리가 71일째 `open`이었다.
- 변경:
  - `backend/tools/digest/retro.py` (신규), `backend/tools/digest/__main__.py` (`--no-evaluate`)
  - `backend/app/services/analysis_service.py` (`latest_close`, `close_on`)
  - `backend/app/services/retrospective_service.py` (`price_fn` 시그니처: `(ticker, due_date)`)
  - `backend/app/routers/retrospective_router.py`, `backend/app/services/scheduler_service.py` (호출부)
  - `backend/tests/test_digest_retro.py` (신규 13), `test_digest_cli.py` (+3), `test_retrospective.py` (+1, 시그니처)
  - `README.md`, `docs/SCHEDULING.md`
- 검증:
  - `pytest -q` → **266 passed** (247 → 266).
  - 실 DB로 확인: `open` 2건이 채점됨. 백업 후 진행.
  - `close_on` 정확도 확인: `close_on("005930", 2026-06-21)` → **353,500**. 6월 21일은 일요일이라 다음 거래일(6/22) 종가를 집는다. 오늘 종가(261,500)가 아니다.
- **작업 중 발견한 결함 (T19 안에서 같이 수정)**: 배선만 붙이고 돌렸더니 71일 밀린 추천이 **+273.57%** 로 채점됐다. `evaluate_due()`가 **현재가**로 재고 있었다. horizon 5일짜리를 71일 뒤에 채점하면 71일 수익률이 5일 성과로 남는다. 적중률·평균수익이 전부 그 위에 쌓이므로 회고 기능의 숫자가 통째로 거짓이 된다.
  - `close_on(ticker, date)`를 만들어 **추천일 + horizon 시점의 종가**로 채점하게 바꿨다. 휴장이면 다음 거래일.
  - 실 DB를 채점 직전 백업으로 되돌리고 올바른 기준으로 재채점했다.
- 결정:
  - **기본은 채점한다.** 스케줄러를 안 켠 상태가 기본값인데 거기서 회고가 죽어 있으면 기능이 없는 것과 같다. `--no-evaluate`로 끈다.
  - **T04 규칙("digest는 DB를 읽기만")의 목적은 지킨다** — digest는 새 추천을 만들지 않는다. 이미 있는 기록에 결과를 채워 넣을 뿐이다.
  - **채점 실패가 리포트를 죽이지 않는다.** 가격 조회는 네트워크를 타므로 실패할 수 있다. 예외를 올리지 않고 메시지로 돌려준다.
  - **가격을 못 받으면 `open`으로 둔다.** 0%로 채점하면 통계가 거짓말을 한다.
  - 조회 기간은 간격에 맞춰 가장 짧은 것을 고른다(`1mo` → `3y`). 71일 전이면 `1y`면 충분하고 매번 `3y`를 긁을 이유가 없다.
- **잡은 테스트 오염 1건**: `test_digest_retro.py`가 싱글턴 **인스턴스**에 `fetch_ohlcv`를 심었더니, monkeypatch teardown이 그 자리에 바운드 메서드를 되돌려 놓아 이후 라우터 테스트의 **클래스** 레벨 패치가 그 인스턴스에서만 가려졌다. 단독 실행은 통과하고 전체 실행만 5건 깨졌다. 클래스 패치로 바꿔 해결.
- **남은 데이터 문제 (코드 아님)**: 005930 추천의 `price_at_rec`가 70,000원인데 2026-06-17 실제 종가는 346,500원이다. 시드/테스트로 들어간 가짜 레코드로 보이고, 그래서 채점 결과가 +405%로 나온다. 회고 통계가 이 한 건 때문에 왜곡된다. 사용자 데이터라 임의로 지우지 않았다.
- 다음: T20 종목 화면에 전환 횟수.

## [T20] 분석 화면에 그 종목 전환 횟수
- 일시: 2026-08-26 22:07
- 상태: 완료
- 목적: 신호를 보는 그 화면에서 "이 신호를 얼마나 믿을지"가 같이 읽히게 한다. 지금까지는 리서치 탭까지 가야 알 수 있었다.
- 변경:
  - 백엔드: `signal_history_service.summary(ticker=...)`, `GET /retrospective/signal-changes?ticker=`
  - 프론트: `lib/api.ts`, `lib/types.ts`, `hooks/queries.ts`(`useTickerFlipCount`), `components/SignalCard.tsx`, `components/AnalysisView.tsx`
  - 테스트: 백엔드 +4, `SignalCard.test.tsx` +3, `signal-history.spec.ts` +1
- 검증: 백엔드 **270 passed**, 프론트 `vitest`·`lint`·`format:check`·`next build` 통과, `playwright` **52 passed**.
- 결정:
  - **훅을 조기 반환보다 위에 뒀다.** `AnalysisView`는 로딩·오류일 때 먼저 반환한다. 훅을 그 아래 두면 렌더마다 훅 개수가 달라진다. 종목이 없으면 훅이 조회를 미룬다.
  - **`SignalCard`는 여전히 표시만 한다.** 카드가 직접 조회하면 테스트가 네트워크를 알아야 한다. 횟수는 prop 으로 받는다.
  - **다른 종목의 숫자를 잠깐이라도 보여주지 않는다.** 응답의 `ticker` 가 지금 보는 종목과 다르면 0으로 친다. 종목을 바꾸면 이전 종목 요청이 늦게 도착할 수 있다.
  - **이력이 없으면 아무것도 그리지 않는다.** digest 를 한 번도 안 돌렸으면 0이고, 그건 고장이 아니다. 2회 미만도 마찬가지 — 1회는 그 전환 자체다.
  - 데모 픽스처의 `ticker` 를 `005930` 으로 뒀다. 정적 파일이라 `?ticker=` 로 갈라줄 수 없는데, 데모에 분석 데이터가 있는 종목이 그것뿐이다. 그래야 배지가 데모에서도 보인다.
- **CI가 잡은 것 (내 확인 절차 오류)**: `SignalHistoryPanel.test.tsx` 2건이 깨진 채로 PR을 올렸다. 훅 시그니처가 `(days, ticker)` 로 바뀌어 호출 인자가 `(30, undefined)` 가 됐는데 테스트는 `[30]` 을 기대하고 있었다. 로컬에서도 실패하고 있었는데, 게이트 출력을 `Select-Object -Last 3` 으로 잘라 pass/fail 줄을 못 본 채 "전부 통과"로 판단했다. 이후로는 출력에서 `Test Files`/`Tests` 줄을 명시적으로 뽑아서 본다.
- **관찰**: e2e 한 번에 원인 불명 1건 실패 후 3회 연속 통과. 실패한 테스트 이름이 출력에 남지 않아 특정하지 못했다. 재현되면 다시 본다.
- 다음: T21 배포·측정, T22 마감.

## [T21] 배포 확인과 Lighthouse 재측정
- 일시: 2026-08-26 22:35
- 상태: 완료
- 목적: 어제·오늘 올린 UI가 실제 배포에 반영됐는지 확인하고, 성능 수치를 갱신한다.
- 변경: `README.md` (측정 섹션)
- 검증:
  - Pages 배포 `1a199e9` **success**. 데모 API `retrospective/signal-changes` → 200, 새 스키마(`ticker`, `kind`) 확인.
  - **배포된 화면에서 직접 확인**: 분석 탭 종합 신호 아래 "최근 30일 3번 뒤집힘 — 그만큼 덜 믿을 근거"가 실제로 렌더된다. 리서치 탭 패널도 DOM에 있다(탭 미선택이라 `hidden`).
  - Lighthouse 12.8.2(직전 측정과 같은 버전) 모바일 7회 · 데스크톱 3회.
- 결과:

| | 모바일 | 데스크톱 |
| --- | --- | --- |
| Performance | 59 (49–70) | 83 (83–84) |
| Accessibility / Best Practices / SEO | 100 | 100 |

- 결정:
  - **모바일은 3회로 재지 않는다.** 처음 3회가 [49, 70, 51]로 나와 중앙값 51이었는데, 7회로 늘리니 중앙값 59에 범위 49~70이었다. 3회 중앙값은 이 폭 안에서 아무 값이나 될 수 있다. README에 범위를 같이 적어, 다음에 재는 사람이 한 번 재고 "좋아졌다"고 말하지 않게 했다.
  - 직전 측정(08-22, 모바일 60 / 데스크톱 84) 대비 **변동 없음**. 리서치 패널과 전환 횟수 배지를 더했는데도 노이즈 범위 안이다. 접근성 100도 그대로 — 새 UI 두 개가 기준을 깨지 않았다.
  - 데스크톱 CLS는 여전히 0.271. 알려진 빚이고 이번에 손대지 않았다.
- **관찰**: 분석 화면이 이제 종목당 요청을 하나 더 보낸다(전환 횟수). 성능 수치에는 드러나지 않았다.
- 다음: T22 마감.

## [T22] 가짜 추천 레코드 정리
- 일시: 2026-08-26 23:05
- 상태: 완료
- 목적: T19에서 발견한 데이터 문제. 회고 적중률이 실제 기록이 아닌 값 위에 쌓이고 있었다.
- 변경: 코드 변경 없음. 실 DB `recommendations` 2건 삭제.
- 검증:
  - **삭제 전에 실제 시세와 대조해 판별했다.** 각 추천의 `price_at_rec` 를 그 날짜 종가와 비교:

| id | 티커 | 추천일 | 기록가 | 실제 종가 | 괴리 | 판정 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 005930 | 2026-06-16 | 70,000 | 343,000 | -79.6% | 가짜 |
| 2 | 000660 | 2026-06-10 | 100,000 | 2,048,000 | -95.1% | 가짜 |
| 3 | 001450 | 2026-08-10 | 41,000 | 41,000 | 0.0% | 실제 |

  - 살린 001450은 채점값도 확인했다 — horizon(8/15 토요일)의 다음 거래일 8/18 종가 49,700, +21.22%. 실제 시세와 맞는다.
  - 삭제 직전 백업: `quant_app.db.bak-20260826-*-before-cleanup`.
  - 정리 후 요약: `total=1, evaluated=1, open=0, hit_rate=1.0, avg_return=21.22`.
- 결정:
  - **괴리 20%를 넘는 것만 지웠다.** 세 건을 한 번에 비우는 편이 간단하지만, 001450은 추천일 종가와 정확히 일치하는 진짜 기록이다. 진짜를 같이 버리면 회고가 처음부터 다시 시작한다.
  - **표본 1건의 적중률 100%는 아직 아무 의미가 없다.** 숫자가 그럴듯해 보이는 것과 믿을 만한 것은 다르다. digest가 매일 돌면서 쌓여야 한다.
- **출처 추정**: 두 건 다 값이 지나치게 둥글다(70,000 / 100,000 → 110,000, 정확히 +10%). **테스트가 실 DB에 쓴 흔적으로 보인다** — T09에서 `test_digest_cli.py` 가 `SessionLocal` 을 패치하지 않아 실 DB에 접근하던 것을 잡았고, 같은 종류의 누수가 예전에도 있었을 가능성이 크다. 지금은 테스트가 임시 DB로 격리돼 있어 같은 경로로는 재발하지 않는다.

## [T23] 폰트 스타일시트를 번들로 내려 렌더 블로킹 제거
- 일시: 2026-08-27 21:30
- 상태: 완료
- 목적: 알려진 빚 3번. 첫 픽셀을 그리기 전에 외부 CDN 왕복을 한 번 기다리고 있었다.
- 변경: `frontend/app/fonts.css` (신규), `frontend/app/layout.tsx`
- 검증:
  - `npm run format:check` / `npm run lint` 통과.
  - `npm test` → `Test Files 11 passed (11)`, `Tests 162 passed (162)`.
  - `npx playwright test` → `52 passed (29.0s)`.
  - `npm run build` 성공. 생성된 `index.html` 의 `<link rel="stylesheet">` 두 개가 모두 `/_next/static/chunks/*.css` 다. **jsdelivr 스타일시트 링크가 사라진 것을 출력에서 직접 확인했다.**
  - CSS 번들: 기존 chunk 27,036B(gzip 6,059B) + 새 폰트 chunk 57,359B(gzip 12,846B).
- 결정:
  - **next/font 로 가지 않았다.** ARCHITECTURE 에 "next/font 가 제대로 된 해법"이라고 적어뒀지만, 실제 파일을 재보니 그 길이 막혀 있다. Pretendard dynamic subset 은 92 조각(≈3.2MB)이고 통짜 variable woff2 는 2.0MB 다. `next/font/local` 은 `unicode-range` 를 표현할 수 없어 조각을 못 쓴다 — 즉 next/font 로 가면 **모든 방문자가 2.0MB 를 한 번에 받는다.** 지금은 실제 쓰이는 조각 몇 개만 받는다. 성능을 고치려던 작업이 성능을 깎는다.
  - **막고 있던 것은 폰트 파일이 아니라 스타일시트였다.** 그래서 `@font-face` 선언 92개만 `app/fonts.css` 로 가져와 앱 CSS 번들에 넣고, `url()` 은 CDN 절대 경로로 바꿨다. 렌더 전에 기다리는 외부 요청이 이제 없다. woff2 는 여전히 CDN 에서 오지만 `font-display: swap` 이라 렌더를 막지 않는다.
  - **preconnect 는 남겼다.** 이제 스타일시트가 아니라 woff2 를 위한 것이다. 주석도 그렇게 고쳤다.
  - **선언을 `globals.css` 에 합치지 않고 파일을 나눴다.** 92개는 생성물이고 우리가 손으로 고칠 것이 아니다. 갱신 절차를 파일 머리 주석에 적어뒀다.
- **주의**: 3rd-party 의존이 없어진 것은 아니다. 스타일시트 왕복 하나가 없어졌을 뿐, woff2 는 그대로 jsdelivr 에서 온다. CDN 이 죽으면 fallback 폰트로 렌더된다(그전에도 그랬다).
- 다음: T24 로딩 스켈레톤 CLS.

## [T24] 레이아웃 흔들림(CLS) 원인 재조사와 수정
- 일시: 2026-08-27 22:10
- 상태: 완료
- 목적: 알려진 빚 2번. 데스크톱 CLS 0.271 (기준 0.1).
- 변경: `frontend/tests/layout-shift.spec.ts` (신규), `frontend/app/page.tsx`, `frontend/components/WatchlistRail.tsx`, `frontend/components/AnalysisView.tsx`, `frontend/components/StockSearch.tsx`
- 검증:
  - **고치기 전에 먼저 쟀다.** `layout-shift` PerformanceObserver 로 shift 마다 `sources` 를 찍어봤다. 데스크톱 1350×940 에서 총 0.273 — Lighthouse 가 보고한 0.271 과 같은 값이다.
  - 모바일 375×812 도 같이 쟀다. **0.386.** 지금까지 아무도 재지 않은 값이고, 데스크톱보다 나빴다.
  - 수정 후 재측정: 데스크톱 **0.030**, 모바일 **기준 통과**. `npx playwright test` → `54 passed (25.1s)` (기존 52 + 신규 2).
  - `npm run format:check` / `npm run lint` / `npm test` (`162 passed`) 통과.
- 결정:
  - **문서에 적힌 원인이 틀렸다.** ARCHITECTURE 에는 "분석 스켈레톤이 아래를 밀어낸다"라고만 적혀 있었다. 실제로 재보니 원인이 셋이었고, 데스크톱에서 제일 큰 것은 스켈레톤이 아니라 **좌측 레일**이었다. 관심 목록이 스켈레톤 3줄에서 실제 목록으로 바뀌며 높이가 변하는데, 위의 발굴 레일이 `flex-1` 이라 그만큼 줄었다 늘었다 하면서 두 목록의 항목이 통째로 밀렸다. 짐작으로 고쳤으면 스켈레톤만 만지고 값은 그대로였을 것이다.
  - **모바일 원인은 2px 였다.** 검색 버튼의 아이콘이 로딩 스피너(16px)에서 돋보기(18px)로 바뀐다. 그 2px 때문에 375px 폭에서 버튼이 다음 줄로 넘어가고, 폼이 58px 자라면서 본문 전체가 그만큼 밀렸다. 아이콘 자리를 18×18 로 고정했다. 정상 상태의 폼 높이(184px)는 그대로다 — 이전에도 로딩이 끝나면 3줄이었다.
  - **관심 목록은 lg 에서만 높이를 고정했다.** `lg:h-[300px]` 안에서 목록만 스크롤한다. lg 아래에서는 레일이 본문 위에 쌓이므로 고정할 이유가 없고, 고정하면 좁은 화면에서 목록을 보려고 스크롤을 두 번 하게 된다.
  - **스켈레톤은 min-height 를 박지 않고 실제 순서대로 블록을 늘렸다.** ARCHITECTURE 가 경고한 "큰 min-height" 는 오류·빈 상태에서 빈 화면이 남는다는 얘기였는데, 그 둘은 스켈레톤보다 위에서 조기 반환하므로 이 함수를 타지 않는다. 그래서 블록을 실제 화면 앞부분(배지 → 히어로 → 차트+신호 → 심리+목표가 → 수급+뉴스)과 같은 순서·높이로 채웠다.
  - **테스트로 잠갔다.** `tests/layout-shift.spec.ts` 가 데스크톱·모바일 두 폭에서 CLS < 0.1 을 검사한다. jsdom 에는 레이아웃 엔진이 없어 단위 테스트로는 만들 수 없는 값이고, Lighthouse 는 CI 에서 돌지 않는다. 이 값이 다시 나빠지면 이제 PR 에서 걸린다.
- **관찰**: 모바일 값을 이번에 처음 쟀다. README 의 측정 표에는 Performance 점수만 있었고 CLS 는 데스크톱만 적혀 있었다. 재지 않은 것은 좋아 보이는 게 아니라 모르는 것이다.
- 다음: T25 `lib/types.ts` 분할.

## 남은 작업 (다음 세션)
- **T07** 작업 스케줄러 등록 안내 — `schtasks` 명령과 확인 절차. 등록 자체는 사용자가 직접.
- **T08** 알림 — 신호 변화가 있을 때만 Windows 토스트 또는 메일. 변화 없는 날 알림이 오면 곧 무시하게 된다.
- **T09** 신호 변화 이력을 별도 테이블로. 지금은 JSON 스냅샷 비교라 "지난달에 몇 번 뒤집혔나"를 못 본다. `retrospective_service`가 먹을 수 있는 형태가 되면 리서치 탭과 연결된다.
- **부채(T03에서 발견, 범위 밖)**: `scheduler_service`가 `market_router._buy_signals_payload`와 `surge_router.scan_surge`를 import한다. `market_router`는 `StockDataProvider()`를 자체 생성해 `analysis_service`와 인스턴스가 갈린다.
