# Quant Insight Backend

FastAPI 기반 투자 참고용 분석 API입니다. 한국 주식은 `pykrx` 우선, `FinanceDataReader` 보조 provider를 사용하고 해외 영문 티커는 `yfinance`를 사용합니다.

## 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

PowerShell 실행 정책 때문에 activate가 막히면 다음 명령을 사용합니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## 환경변수

```env
DATABASE_URL=sqlite:///./quant_app.db
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATA_PROVIDER=auto
ALLOW_SAMPLE_FALLBACK=false
LOG_DATA_PROVIDER_ERRORS=true
BUY_SIGNAL_KR_LIMIT=100
BUY_SIGNAL_US_LIMIT=100
BUY_SIGNAL_BATCH_SIZE=10
BUY_SIGNAL_MAX_WORKERS=5
BUY_SIGNAL_ITEM_TIMEOUT_SECONDS=25
BUY_SIGNAL_REFRESH_SECONDS=60
DATA_PROVIDER_TIMEOUT_SECONDS=12
DATA_CACHE_TTL_SECONDS=60
UNIVERSE_CACHE_TTL_SECONDS=3600
SAMPLE_DATA_SEED=42
```

`ALLOW_SAMPLE_FALLBACK=false`이면 실데이터 조회 실패 시 샘플 데이터로 대체하지 않고 오류를 반환합니다. `true`로 설정하면 개발용 샘플 데이터를 반환하되 `source="sample"`, `is_sample=true`가 포함됩니다.

## 주요 API

- `GET /api/health`
- `GET /api/debug/data-provider/{ticker}`
- `GET /api/stocks/{ticker}/price?period=1y`
- `GET /api/stocks/{ticker}/analysis?period=1y`
- `GET /api/stocks/{ticker}/prediction?period=1y`
- `GET /api/stocks/{ticker}/signal?period=1y`
- `GET /api/stocks/{ticker}/backtest?period=1y&initial_capital=10000000`
- `GET /api/watchlist`
- `POST /api/watchlist`
- `DELETE /api/watchlist/{ticker}`

## 대표 종목과 매수 신호 API

```text
GET /api/market/representative-stocks?market=all&kr_limit=100&us_limit=100&source=auto
GET /api/market/buy-signals?market=all&min_signal=WEAK_BUY&kr_limit=100&us_limit=100&limit=20&include_sample=false&source=auto&sort_by=signal&force_refresh=false
```

`representative-stocks`는 동적 수집을 먼저 시도하고 실패 시 fallback 목록을 사용합니다. `buy-signals`는 종목별 가격 데이터와 분석 결과에 TTL 캐시를 적용하고, `BUY_SIGNAL_BATCH_SIZE`, `BUY_SIGNAL_MAX_WORKERS` 설정으로 외부 provider 호출량을 제한합니다.

일부 종목 분석 실패는 전체 실패로 처리하지 않고 `failed_items`에 포함합니다. 응답에는 `kr_checked`, `us_checked`, `total_success`, `total_failed`, `total_matched`, `strong_buy_count`, `buy_count`, `weak_buy_count`가 포함됩니다.

## 성능 주의사항

국내 100개와 해외 100개를 동시에 분석하면 외부 데이터 제공자의 응답 지연 또는 rate limit 영향을 받을 수 있습니다. `BUY_SIGNAL_ITEM_TIMEOUT_SECONDS`와 `DATA_PROVIDER_TIMEOUT_SECONDS`로 느린 provider 호출을 제한하며, 제한 시간을 넘긴 종목은 `failed_items`에 포함됩니다. 개발 중에는 `source=fallback`, `kr_limit`, `us_limit`, `limit`을 낮춰 먼저 확인한 뒤 전체 분석을 실행하는 것이 좋습니다.

## 투자 유의사항

본 서비스의 분석, 예측, 매수/매도 신호는 과거 데이터와 알고리즘을 기반으로 한 참고 정보입니다. 실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.

## 신호 엔진 v2

대부분의 종목이 HOLD로 남는 문제를 줄이기 위해 절대 점수와 cross-section 상대순위를 함께 사용합니다. 단일 종목 API는 `final_buy_score`, `final_sell_score`, `risk_score`, `ml_up_probability`, `market_regime`을 기준으로 신호를 계산합니다. `/api/market/buy-signals`는 분석 대상 universe 전체를 먼저 계산한 뒤 `buy_score_percentile`, `sell_score_percentile`, `relative_strength_rank`, `liquidity_rank`, `risk_rank`를 적용해 상대적으로 강한 후보를 선별합니다.

추가 서비스:

- `ranking_service.py`: 매수/매도 점수, 20일 상대강도, 유동성, 리스크 상대순위 계산
- `regime_service.py`: BULL_TREND, BEAR_TREND, SIDEWAYS, HIGH_VOLATILITY, RECOVERY, BEAR_CRASH 시장국면 판별
- `ml_signal_service.py`: RandomForestClassifier 기반 5거래일 상승확률 추정
- `korean_market_service.py`: 국내 주식 수급, 거래대금, 시장경보 반영을 위한 확장 구조

`/api/market/buy-signals` 응답에는 `market_regime`, `buy_score_percentile`, `sell_score_percentile`, `relative_strength_rank`, `liquidity_rank`, `ml_up_probability`, `final_buy_score`, `final_sell_score`, `signal_source`, `hold_reasons`가 포함됩니다. 일부 종목 분석 실패는 `failed_items`에 담기며 전체 API 응답은 유지됩니다.

백테스트 API는 `strategy` query parameter를 지원합니다.

```text
GET /api/stocks/AAPL/backtest?period=1y&initial_capital=10000000&strategy=regime_adjusted_strategy
```

지원 전략은 `absolute_score_strategy`, `percentile_rank_strategy`, `ml_probability_strategy`, `regime_adjusted_strategy`입니다.

## 실시간 운용 API — 없음

예전 이 자리에 `live_trading_engine`, `broker_adapter`, `risk_guard` 같은 서비스와
`/api/live/*` 엔드포인트가 문서화돼 있었습니다. **그 코드는 저장소에 없습니다.**
설계 단계에서 지워졌는데 문서만 남아 있었습니다(2026-08-22 확인).

이 앱은 분석 전용입니다. 주문 실행 기능은 포함하지 않으며, 매매는 외부 증권사 앱에서
하고 분석 결과는 CSV로 내보냅니다. 계획은 [루트 README의 로드맵](../README.md#로드맵)에
한 줄로 남아 있습니다.
