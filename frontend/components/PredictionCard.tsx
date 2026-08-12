import type { HorizonPrediction } from "@/lib/types";

export default function PredictionCard({ predictions }: { predictions: HorizonPrediction[] }) {
  return (
    <section className="card">
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">가격 예측</p>
          <h2 className="mt-0.5 text-heading text-ink">미래 가격 시뮬레이션</h2>
        </div>
        <span className="text-xs font-medium text-muted">Walk-forward 검증</span>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {predictions.map((prediction) => {
          const up = prediction.expected_return_pct >= 0;
          return (
            <div
              key={prediction.horizon_days}
              className="rounded-xl bg-surface px-3 py-3.5 transition-colors hover:bg-surface2"
            >
              <p className="text-xs font-semibold text-muted">{prediction.horizon_days}일 후</p>
              <p className="mt-2 text-lg font-bold text-ink tabular">
                {prediction.predicted_price.toLocaleString()}
              </p>
              <p className={`mt-1 text-sm font-bold tabular ${up ? "text-up" : "text-down"}`}>
                {up ? "+" : ""}{prediction.expected_return_pct.toFixed(2)}%
              </p>
              <div className="mt-3 flex items-center gap-1.5">
                <div className="h-1 flex-1 rounded-full bg-bg overflow-hidden">
                  <div
                    className="h-1 rounded-full bg-toss"
                    style={{ width: `${prediction.confidence_score}%` }}
                  />
                </div>
                <span className="text-[10px] font-bold text-muted tabular">{prediction.confidence_score}</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-4 text-xs leading-5 text-muted">
        예측값은 과거 데이터 기반 통계 모델의 산출값입니다. 실거래 시 외부 증권사 앱에서 직접 확인 후 매매하세요.
      </p>
    </section>
  );
}
