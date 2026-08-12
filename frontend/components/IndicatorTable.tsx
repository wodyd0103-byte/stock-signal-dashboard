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
            // 좁을 때는 이름/값, 영향/기여도, 해석 순으로 접는다.
            //
            // 한 줄로 펴는 시점이 lg(1024px)가 아니라 xl(1280px)인 이유: 이 테이블이
            // 실제로 받는 폭은 뷰포트가 아니라 본문 열의 폭이다. lg부터 320px 좌측
            // 레일이 생기므로 1024px에서 본문은 656px뿐이고, 고정 4열 420px을 빼면
            // 해석 열에 124px밖에 안 남아 행 높이가 80px까지 늘어난다(1440px에서는 44px).
            // xl에서는 본문이 912px이라 해석 열이 444px 확보된다.
            <div
              key={indicator.name}
              className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface xl:grid-cols-[140px_120px_90px_70px_1fr] xl:gap-3"
            >
              <p className="text-sm font-bold text-ink">{indicator.name}</p>
              <p className="text-right text-sm font-bold text-ink tabular xl:text-left">
                {String(indicator.value ?? "-")}
              </p>
              <span
                className={`chip justify-self-start text-xs xl:justify-self-stretch ${influenceStyle(indicator.influence)}`}
              >
                {indicator.influence}
              </span>
              <p className={`text-sm font-bold tabular text-right ${contribClass}`}>
                {contribution > 0 ? "+" : ""}{contribution}
              </p>
              <p className="col-span-2 text-xs leading-5 text-muted xl:col-span-1">
                {indicator.interpretation}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
