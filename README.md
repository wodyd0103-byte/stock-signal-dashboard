# Quant Insight

실제 주식 가격 데이터를 우선 조회해 투자 참고용 분석, 기술적 지표, 단기 가격 예측, 리스크 분석, 백테스트, 매수/매도/관망 신호를 제공하는 웹 애플리케이션입니다. 실제 주문 실행 기능은 없으며, 모든 신호는 알고리즘 기반 참고 정보입니다.

## 구성

- `backend`: FastAPI, SQLite, pandas, numpy, scikit-learn, yfinance, pykrx, FinanceDataReader
- `frontend`: Next.js, TypeScript, Tailwind CSS, Recharts

## 실행

백엔드:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

PowerShell 실행 정책 때문에 activate가 막히면 다음처럼 실행할 수 있습니다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

프론트엔드:

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000/dashboard` 또는 `http://localhost:3000/buy-signals`를 엽니다.

## 주요 기능

- `/dashboard`: 종목 검색, 가격 차트, 종합 신호, 기술적 지표, 리스크, 예측 가격
- `/watchlist`: 관심종목 목록과 신호 요약
- `/backtest`: 다음 거래일 체결 기준 백테스트
- `/buy-signals`: 국내 대표 최대 100개, 해외 대표 최대 100개 종목의 매수 구간 신호 주기적 모니터링
- `/settings`: 데이터 제공자, 분석 파라미터, 투자 유의사항 안내

## 데이터 제공자와 fallback

`DATA_PROVIDER=auto`가 기본값입니다. 6자리 숫자 또는 `.KS`, `.KQ` 티커는 한국 주식으로 판단해 `pykrx`를 우선 사용하고 실패 시 `FinanceDataReader`를 시도합니다. 영문 티커는 해외 주식으로 판단해 `yfinance`를 사용합니다.

`ALLOW_SAMPLE_FALLBACK=false`가 기본값이므로 실데이터 조회 실패 시 샘플 데이터로 조용히 넘어가지 않고 명확한 오류를 반환합니다. 개발 중 샘플 fallback을 허용하려면 `backend/.env`에 `ALLOW_SAMPLE_FALLBACK=true`를 설정하세요. 이 경우 API와 화면에 `source="sample"`, `is_sample=true`가 표시됩니다.

## 100+100 매수 신호 모니터

`/api/market/representative-stocks`는 `source=auto`일 때 KRX/pykrx와 주요 미국 지수 구성 종목 수집을 우선 시도하고, 실패하면 `backend/app/core/stock_universe.py`의 fallback 목록을 사용합니다.

`/api/market/buy-signals`는 대표 종목을 배치 단위로 제한된 병렬 worker에서 분석합니다. 일부 종목이 실패해도 전체 응답은 유지되며 실패 종목은 `failed_items`에 담깁니다.

예시:

```text
GET http://127.0.0.1:8000/api/market/representative-stocks?market=all&kr_limit=100&us_limit=100&source=auto
GET http://127.0.0.1:8000/api/market/buy-signals?market=all&min_signal=WEAK_BUY&kr_limit=100&us_limit=100&limit=20&include_sample=false&source=auto&sort_by=signal
```

주요 환경변수:

```env
BUY_SIGNAL_KR_LIMIT=100
BUY_SIGNAL_US_LIMIT=100
BUY_SIGNAL_BATCH_SIZE=10
BUY_SIGNAL_MAX_WORKERS=5
BUY_SIGNAL_ITEM_TIMEOUT_SECONDS=25
BUY_SIGNAL_REFRESH_SECONDS=60
DATA_PROVIDER_TIMEOUT_SECONDS=12
DATA_CACHE_TTL_SECONDS=60
UNIVERSE_CACHE_TTL_SECONDS=3600
```

외부 데이터 제공자는 네트워크 상태, 장 운영 시간, rate limit에 따라 응답이 지연되거나 실패할 수 있습니다. `BUY_SIGNAL_ITEM_TIMEOUT_SECONDS`와 `DATA_PROVIDER_TIMEOUT_SECONDS`를 넘긴 종목은 `failed_items`로 분리되며 전체 응답은 유지됩니다. worker 수와 TTL을 지나치게 공격적으로 낮추면 provider 제한에 걸릴 수 있습니다.

## 투자 유의사항

본 서비스의 분석, 예측, 매수/매도 신호는 과거 데이터와 알고리즘을 기반으로 한 참고 정보입니다. 실제 투자 결과를 보장하지 않으며, 모든 투자 판단과 책임은 사용자 본인에게 있습니다.

## 신호 엔진 v2

기존 신호 엔진은 절대 점수 기준만 사용했기 때문에 시장 전체가 애매한 날에는 많은 종목이 HOLD로 분류될 수 있었습니다. 현재 엔진은 단일 종목 분석에서는 최종 보정 점수를 사용하고, `/buy-signals` 같은 다종목 모니터에서는 200개 대표 종목 안에서의 상대순위 percentile을 함께 사용합니다.

- `raw_buy_score`, `raw_sell_score`: 기술적 지표 기반 원점수입니다.
- `final_buy_score`, `final_sell_score`: 시장국면, ML 상승확률, 유동성, 상대강도, 국내 수급 구조를 반영한 최종 점수입니다.
- `buy_score_percentile`, `sell_score_percentile`: 대표 종목 universe 안에서 상대적으로 얼마나 높은 점수인지 나타냅니다.
- `market_regime`: BULL_TREND, BEAR_TREND, SIDEWAYS, HIGH_VOLATILITY, RECOVERY, BEAR_CRASH 중 하나로 표시됩니다.
- `ml_up_probability`: 5거래일 후 +2% 이상 상승 여부를 RandomForestClassifier 기반 확률로 추정합니다. 데이터가 부족하면 null로 반환하고 앱은 기존 점수 기반으로 계속 동작합니다.
- 국내 주식은 외국인/기관 수급, 거래대금, 시장경보 데이터를 반영할 수 있는 `korean_market_service` 구조를 포함합니다. 제공자 조회 실패 시 전체 분석은 실패하지 않고 관련 오류만 기록합니다.

다종목 매수 신호 모니터는 상대순위 기준으로 STRONG BUY, BUY, WEAK BUY 후보를 우선 표시합니다. 하락장 또는 고변동성 장에서는 리스크 조건을 더 엄격하게 적용하며, HOLD 종목에는 리스크, 유동성, 시장국면, 상대순위 부족 등 판단 이유를 함께 제공합니다.

백테스트는 다음 전략 비교를 제공합니다.

- `absolute_score_strategy`: 절대 점수 기반 전략
- `percentile_rank_strategy`: 상대순위 기반 전략
- `ml_probability_strategy`: ML 상승확률 기반 전략
- `regime_adjusted_strategy`: 시장국면 보정 전략

이 애플리케이션은 실제 주문 기능을 포함하지 않으며, 실거래 API 연동은 추후 확장 가능한 구조만 제공합니다.

## 실시간 운용

`/live-trading` 페이지가 추가되었습니다. 기존 `/backtest`는 전략 검증용으로 유지하고, 실제 화면의 중심은 paper trading 기반 실시간 운용 대시보드로 확장했습니다.

기본 안전 정책:

- 기본 운용 모드는 `paper`입니다. 실제 주문은 실행되지 않습니다.
- 실거래 주문은 `TRADING_MODE=live`, `LIVE_TRADING_ENABLED=true`, `ENABLE_ORDER_EXECUTION=true`, 지원 broker, 서버 `.env`의 API Key, 프론트 실거래 위험 확인, `emergency_stop=false`를 모두 만족해야만 허용됩니다.
- API Key, App Secret, Access Token은 프론트엔드로 전달하지 않습니다.
- `.env`, `backend/.env`, `frontend/.env.local`은 `.gitignore`에 포함되어 있습니다.
- sample fallback 데이터 기반 주문은 차단되고 `orders.status=REJECTED`로 기록됩니다.

지원 전략 모드:

- 단타: 짧은 보유 기간, 빠른 갱신, 손절 2%, 익절 3%, 최대 보유 3일 기본값
- 단기투자: 1개월 이내 운용, 손절 5%, 익절 8%, 최대 보유 30일 기본값
- 장기투자: 6개월 이내 운용, 손절 10%, 익절 20%, 최대 보유 180일 기본값

각 모드는 독립적으로 ON/OFF, 할당 예산, 최대 보유 종목 수, 종목당 최대 비중, 손절/익절, 보유 기간, 시장, 허용 티커, 최소 신호, 리스크 제한을 설정할 수 있습니다. 여러 모드를 동시에 RUNNING 상태로 둘 수 있으며, `ResourceManager`가 전체 예산과 모드별 예산을 기준으로 과투자를 차단합니다.

실시간 운용 API:

```text
GET  /api/live/status
GET  /api/live/performance
GET  /api/live/positions
GET  /api/live/orders
POST /api/live/start
POST /api/live/pause
POST /api/live/stop
POST /api/live/emergency-stop
GET  /api/live/modes
PUT  /api/live/modes/{mode_id}
POST /api/live/modes/{mode_id}/start
POST /api/live/modes/{mode_id}/pause
POST /api/live/modes/{mode_id}/stop
GET  /api/live/settings
PUT  /api/live/settings
POST /api/live/positions/{position_id}/close
```

프론트엔드는 `/live-trading`에서 5초마다 성과, 포지션, 주문 로그를 polling합니다. 갱신 중에도 기존 데이터는 유지됩니다.
