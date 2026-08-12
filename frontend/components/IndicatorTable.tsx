import type { IndicatorDetail } from "@/lib/types";

function influenceStyle(influence: IndicatorDetail["influence"]) {
  if (influence === "매수") return "bg-up/15 text-up";
  if (influence === "매도") return "bg-down/15 text-down";
  return "bg-surface text-sub";
}

export default function IndicatorTable({ indicators }: { indicators: IndicatorDetail[] }) {
  return (
    <section className="card">
      <div className="mb-4 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">기술적 지표</p>
          <h2 className="mt-0.5 text-heading text-ink">현재 값과 신호 기여도</h2>
        </div>
      </div>

      <div className="space-y-1">
        {indicators.map((indicator) => {
          const contribution = indicator.contribution;
          const contribClass =
            contribution > 0 ? "text-up" : contribution < 0 ? "text-down" : "text-muted";
          return (
            // 고정 픽셀 5열은 합이 420px를 넘어 좁은 화면에서 페이지를 가로로 넘긴다.
            // 좁을 때는 이름/값, 영향/기여도, 해석 순으로 접고 lg에서 한 줄로 편다.
            <div
              key={indicator.name}
              className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface lg:grid-cols-[140px_120px_90px_70px_1fr] lg:gap-3"
            >
              <p className="text-sm font-bold text-ink">{indicator.name}</p>
              <p className="text-right text-sm font-bold text-ink tabular lg:text-left">
                {String(indicator.value ?? "-")}
              </p>
              <span
                className={`chip justify-self-start text-xs lg:justify-self-stretch ${influenceStyle(indicator.influence)}`}
              >
                {indicator.influence}
              </span>
              <p className={`text-sm font-bold tabular text-right ${contribClass}`}>
                {contribution > 0 ? "+" : ""}{contribution}
              </p>
              <p className="col-span-2 text-xs leading-5 text-muted lg:col-span-1">
                {indicator.interpretation}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
