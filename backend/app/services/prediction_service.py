from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from app.schemas.prediction import (
    HorizonPrediction,
    ModelPrediction,
    OptimalExit,
    PredictionResponse,
    PriceTarget,
)


SHORT_HORIZONS = [1, 3, 5, 20]   # 단기
LONG_HORIZONS = [60, 120]        # 장기 (약 3개월, 6개월)
ALL_HORIZONS = SHORT_HORIZONS + LONG_HORIZONS


def _horizon_label(days: int) -> str:
    """일수 → 자연어 라벨."""
    if days <= 1: return "내일"
    if days <= 3: return "3일 이내"
    if days <= 5: return "1주 이내"
    if days <= 20: return "약 1개월"
    if days <= 60: return "약 3개월"
    if days <= 120: return "약 6개월"
    return f"{days}일"


FEATURE_COLUMNS = [
    "close",
    "volume",
    "ma5",
    "ma20",
    "ma60",
    "rsi",
    "macd",
    "volatility",
    "return_1d",
    "return_5d",
]

# Walk-forward 검증 설정 (속도/정확도 균형)
WALK_FORWARD_SPLITS = 3      # TimeSeriesSplit 폴드 수 (5→3, 속도 ↑)
WALK_FORWARD_MIN_ROWS = 80   # 폴드 시 최소 학습 데이터
WALK_FORWARD_GAP = 1         # train/test 사이 갭 (look-ahead 방지 강화)
RF_ESTIMATORS = 90           # RandomForest 트리 수 (160→90, 속도 ↑)

# 예측 결과 캐시 (ticker+period+마지막 종가 기준). 같은 데이터 재요청 즉시 응답.
import time as _time
from threading import Lock as _Lock

_pred_cache: dict[tuple, tuple[float, "PredictionResponse"]] = {}
_pred_cache_lock = _Lock()
_PRED_TTL = 600  # 10분


class PredictionService:
    def predict(self, ticker: str, period: str, enriched: pd.DataFrame) -> PredictionResponse:
        if enriched.empty:
            raise ValueError("예측에 사용할 가격 데이터가 없습니다.")

        current_price = float(enriched.iloc[-1]["close"])

        # 캐시 조회 (마지막 종가 + 행수로 데이터 동일성 판단)
        cache_key = (ticker.upper(), period, len(enriched), round(current_price, 2))
        now = _time.time()
        # 1) 메모리 캐시
        with _pred_cache_lock:
            hit = _pred_cache.get(cache_key)
        if hit and (now - hit[0]) < _PRED_TTL:
            return hit[1]
        # 2) 디스크 캐시 (재시작 후에도 유효)
        from app.services import disk_cache
        disk_hit = disk_cache.get("prediction", cache_key, _PRED_TTL)
        if disk_hit is not None:
            with _pred_cache_lock:
                _pred_cache[cache_key] = (now, disk_hit)
            return disk_hit

        # 단기 예측
        short = [self._predict_horizon(enriched, h, current_price) for h in SHORT_HORIZONS]

        # 장기 예측 (데이터 충분 시만)
        long_term: list[HorizonPrediction] = []
        if len(enriched) >= 200:  # 약 10개월 이상 데이터 있을 때만
            long_term = [self._predict_horizon(enriched, h, current_price) for h in LONG_HORIZONS]

        # 최적 매도 시점 + 목표가 계산
        all_preds = short + long_term
        optimal_exit = self._compute_optimal_exit(all_preds, current_price, enriched)
        price_target = self._compute_price_target(long_term or short[-1:], current_price, enriched)

        response = PredictionResponse(
            ticker=ticker.upper(),
            period=period,
            current_price=round(current_price, 2),
            predictions=short,
            long_term_predictions=long_term,
            optimal_exit=optimal_exit,
            price_target=price_target,
            feature_columns=FEATURE_COLUMNS,
            note="예측값은 과거 데이터 기반 통계 모델의 산출값이며 실제 가격을 보장하지 않습니다. 외부 매매 앱 의사결정의 참고용입니다.",
        )
        with _pred_cache_lock:
            _pred_cache[cache_key] = (now, response)
        from app.services import disk_cache
        disk_cache.put("prediction", cache_key, response)
        return response

    def _compute_optimal_exit(
        self,
        predictions: list[HorizonPrediction],
        current_price: float,
        enriched: pd.DataFrame,
    ) -> OptimalExit | None:
        """위험 조정 기대수익이 최고인 horizon을 선택."""
        if not predictions:
            return None

        # 최근 20일 변동성 (연율 기준 X, 단순 일 표준편차 %)
        try:
            recent_vol = float(
                enriched["close"].pct_change().tail(20).std() * 100
            )
        except Exception:
            recent_vol = 5.0
        recent_vol = max(recent_vol, 0.5)  # zero division 방지

        scored = []
        for p in predictions:
            if p.expected_return_pct <= 0:
                continue  # 손실 예상 horizon 제외 (매도 추천 안 함)
            # 위험 조정 점수:
            # 기대수익 × 신뢰도 / sqrt(시간 + 변동성 비중)
            # 짧은 horizon 가산점 (확실성), 장기 horizon 페널티 (불확실성)
            confidence = max(1, p.confidence_score) / 100.0
            time_penalty = (p.horizon_days ** 0.45)  # 약하게 페널티
            vol_factor = 1.0 + recent_vol / 20.0
            raw = p.expected_return_pct * confidence / (time_penalty * vol_factor)
            scored.append((raw, p))

        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]

        # 자연어 근거
        rationale_parts = [
            f"{best.horizon_days}일 후 기대수익 +{best.expected_return_pct:.2f}%",
            f"신뢰도 {best.confidence_score}점",
        ]
        if best.horizon_days <= 5:
            rationale_parts.append("단기 모멘텀 우선")
        elif best.horizon_days <= 20:
            rationale_parts.append("스윙 타이밍 적정")
        else:
            rationale_parts.append("중장기 보유 권장")

        return OptimalExit(
            horizon_days=best.horizon_days,
            horizon_label=_horizon_label(best.horizon_days),
            target_price=best.predicted_price,
            expected_return_pct=best.expected_return_pct,
            confidence_score=best.confidence_score,
            risk_adjusted_score=round(best_score, 3),
            rationale=" · ".join(rationale_parts),
        )

    def _compute_price_target(
        self,
        long_predictions: list[HorizonPrediction],
        current_price: float,
        enriched: pd.DataFrame,
    ) -> PriceTarget | None:
        """장기 도달 가능 가격 시나리오 3종."""
        if not long_predictions:
            return None

        # 가장 긴 horizon 기준
        base = max(long_predictions, key=lambda p: p.horizon_days)

        # 최근 변동성 → 시나리오 폭 결정
        try:
            sigma = float(enriched["close"].pct_change().tail(60).std() * 100)
        except Exception:
            sigma = 2.0
        sigma = max(sigma, 0.5)

        # 시나리오 (보수: -0.6σ, 중립: 모델값, 낙관: +0.8σ) × horizon scale
        scale = (base.horizon_days / 252) ** 0.5  # 시간 누적 변동
        delta_pct = sigma * scale  # %
        base_price = base.predicted_price
        conservative = base_price * (1 - delta_pct * 0.6 / 100)
        optimistic = base_price * (1 + delta_pct * 0.8 / 100)

        # 보수가 현재가보다 낮으면 현재가 근처로 보정
        conservative = max(conservative, current_price * 0.92)

        expected_return = (base_price - current_price) / current_price * 100 if current_price else 0.0
        rationale = (
            f"{base.horizon_days}일 기준 모델 예측 {base_price:,.0f}원. "
            f"최근 변동성 {sigma:.2f}% 반영한 ±시나리오 산출."
        )

        return PriceTarget(
            horizon_days=base.horizon_days,
            conservative_price=round(conservative, 2),
            base_price=round(base_price, 2),
            optimistic_price=round(optimistic, 2),
            current_price=round(current_price, 2),
            expected_return_pct=round(expected_return, 2),
            confidence_score=base.confidence_score,
            rationale=rationale,
        )

    def quick_predict_for_signal(self, ticker: str, period: str, enriched: pd.DataFrame) -> PredictionResponse:
        """매수 신호 모니터용 경량 5일 예측 (walk-forward 검증)."""

        if enriched.empty:
            raise ValueError("예측에 사용할 가격 데이터가 없습니다.")

        current_price = float(enriched.iloc[-1]["close"])
        horizon = 5
        model_df = self._make_supervised(enriched, horizon)

        if len(model_df) < 45:
            prediction = self._naive_prediction(enriched, horizon, current_price)
        else:
            score = self._walk_forward_score(model_df, lambda: LinearRegression(), embargo=horizon)
            final_model = LinearRegression()
            final_model.fit(model_df[FEATURE_COLUMNS], model_df["target"])
            latest_features = enriched[FEATURE_COLUMNS].dropna().tail(1)
            predicted_price = float(final_model.predict(latest_features)[0])
            model_prediction = ModelPrediction(
                model="LinearRegressionFast",
                predicted_price=round(max(predicted_price, 0.01), 2),
                test_score=round(score, 4),
            )
            expected_return = (model_prediction.predicted_price - current_price) / current_price * 100 if current_price else 0.0
            prediction = HorizonPrediction(
                horizon_days=horizon,
                predicted_price=model_prediction.predicted_price,
                expected_return_pct=round(expected_return, 2),
                model_predictions=[model_prediction],
                confidence_score=self._confidence_score([model_prediction], expected_return),
            )

        return PredictionResponse(
            ticker=ticker.upper(),
            period=period,
            current_price=round(current_price, 2),
            predictions=[prediction],
            feature_columns=FEATURE_COLUMNS,
            note="매수 신호 모니터용 경량 5일 예측 (walk-forward 검증). 실제 가격을 보장하지 않습니다.",
        )

    def _predict_horizon(self, enriched: pd.DataFrame, horizon: int, current_price: float) -> HorizonPrediction:
        """단일 horizon 예측. test_score = walk-forward 평균."""
        model_df = self._make_supervised(enriched, horizon)

        if len(model_df) < max(45, WALK_FORWARD_MIN_ROWS):
            return self._naive_prediction(enriched, horizon, current_price)

        latest_features = enriched[FEATURE_COLUMNS].dropna().tail(1)
        model_specs: list[tuple[str, Callable[[], object]]] = [
            ("LinearRegression", lambda: LinearRegression()),
            (
                "RandomForestRegressor",
                lambda: RandomForestRegressor(
                    n_estimators=RF_ESTIMATORS, max_depth=8, random_state=42, min_samples_leaf=3, n_jobs=-1
                ),
            ),
        ]

        model_predictions: list[ModelPrediction] = []
        for model_name, factory in model_specs:
            wf_score = self._walk_forward_score(model_df, factory, embargo=horizon)
            final_model = factory()
            final_model.fit(model_df[FEATURE_COLUMNS], model_df["target"])
            predicted = float(final_model.predict(latest_features)[0])
            model_predictions.append(
                ModelPrediction(
                    model=model_name,
                    predicted_price=round(max(predicted, 0.01), 2),
                    test_score=round(wf_score, 4),
                )
            )

        predicted_price = float(np.mean([item.predicted_price for item in model_predictions]))
        expected_return = (predicted_price - current_price) / current_price * 100 if current_price else 0.0
        confidence = self._confidence_score(model_predictions, expected_return)
        return HorizonPrediction(
            horizon_days=horizon,
            predicted_price=round(predicted_price, 2),
            expected_return_pct=round(expected_return, 2),
            model_predictions=model_predictions,
            confidence_score=confidence,
        )

    def _make_supervised(self, enriched: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """타겟 = horizon일 후 종가. 시계열 누수 방지를 위해 미래 정보 제거."""
        df = enriched.copy()
        df["target"] = df["close"].shift(-horizon)
        df = df.dropna(subset=FEATURE_COLUMNS + ["target"]).reset_index(drop=True)
        return df

    def _walk_forward_score(
        self, model_df: pd.DataFrame, model_factory: Callable[[], object], embargo: int = WALK_FORWARD_GAP
    ) -> float:
        """
        TimeSeriesSplit 기반 walk-forward 검증 (purged/embargo).
        - 시간 순서 유지 (랜덤 셔플 X)
        - 폴드별 train: 누적 과거, test: 다음 구간
        - embargo(=라벨 horizon) 만큼 train/test 갭 → 타겟이 미래 horizon을
          참조하므로 그 구간 학습 표본을 제외해야 look-ahead 누수 차단.
        반환: 폴드별 score 평균 (0~1)
        """
        n = len(model_df)
        if n < WALK_FORWARD_MIN_ROWS:
            return 0.0

        n_splits = min(WALK_FORWARD_SPLITS, max(2, (n - WALK_FORWARD_MIN_ROWS) // 20))
        # embargo를 라벨 horizon에 맞추되, fold가 비지 않도록 test 크기-1로 상한.
        test_size = n // (n_splits + 1)
        gap = max(WALK_FORWARD_GAP, min(int(embargo), max(1, test_size - 1)))
        try:
            tscv = TimeSeriesSplit(n_splits=n_splits, gap=gap)
        except TypeError:
            # 매우 옛 sklearn 호환 (gap 미지원)
            tscv = TimeSeriesSplit(n_splits=n_splits)

        scores: list[float] = []
        x_all = model_df[FEATURE_COLUMNS]
        y_all = model_df["target"]
        for train_idx, test_idx in tscv.split(x_all):
            if len(train_idx) < 30 or len(test_idx) < 5:
                continue
            model = model_factory()
            # sklearn 모델은 clone 가능, 안전하게 새 인스턴스
            try:
                model = clone(model)
            except Exception:
                pass
            model.fit(x_all.iloc[train_idx], y_all.iloc[train_idx])
            pred = model.predict(x_all.iloc[test_idx])
            scores.append(self._model_score(y_all.iloc[test_idx], pred))

        if not scores:
            return 0.0
        return float(np.mean(scores))

    def _naive_prediction(self, enriched: pd.DataFrame, horizon: int, current_price: float) -> HorizonPrediction:
        recent_return = enriched["close"].pct_change().tail(min(20, len(enriched))).mean()
        predicted_price = float(current_price * (1 + float(recent_return or 0)) ** horizon)
        expected_return = (predicted_price - current_price) / current_price * 100 if current_price else 0.0
        model_predictions = [
            ModelPrediction(model="RecentTrendFallback", predicted_price=round(predicted_price, 2), test_score=0.0)
        ]
        return HorizonPrediction(
            horizon_days=horizon,
            predicted_price=round(predicted_price, 2),
            expected_return_pct=round(expected_return, 2),
            model_predictions=model_predictions,
            confidence_score=35,
        )

    def _model_score(self, y_true: pd.Series, y_pred: np.ndarray) -> float:
        if len(y_true) < 2:
            return 0.0
        r2 = max(-1.0, min(1.0, float(r2_score(y_true, y_pred))))
        try:
            mape = float(mean_absolute_percentage_error(y_true, y_pred))
        except ValueError:
            mape = 1.0
        return max(0.0, min(1.0, 0.55 * ((r2 + 1) / 2) + 0.45 * (1 - min(mape, 1))))

    def _confidence_score(self, model_predictions: list[ModelPrediction], expected_return: float) -> int:
        if not model_predictions:
            return 0
        avg_score = float(np.mean([prediction.test_score for prediction in model_predictions]))
        dispersion = float(np.std([prediction.predicted_price for prediction in model_predictions]))
        avg_price = float(np.mean([prediction.predicted_price for prediction in model_predictions]))
        agreement_penalty = min(25, int((dispersion / max(avg_price, 1)) * 100))
        move_penalty = 8 if abs(expected_return) > 12 else 0
        return max(5, min(95, int(avg_score * 100) - agreement_penalty - move_penalty))
