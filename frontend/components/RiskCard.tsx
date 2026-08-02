import type { RiskResponse } from "@/lib/types";

function riskTone(score: number) {
  if (score <= 30) return { color: "text-up", bg: "bg-up/10", label: "낮음" };
  if (score <= 60) return { color: "text-warn", bg: "bg-warnBg", label: "보통" };
  if (score <= 80) return { color: "text-down", bg: "bg-down/10", label: "높음" };
  return { color: "text-down", bg: "bg-down/15", label: "매우 높음" };
}

export default function RiskCard({ risk }: { risk: RiskResponse }) {
  const tone = riskTone(risk.risk_score);

  return (
    <section className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">리스크 분석</p>
          <h2 className="mt-0.5 text-heading text-ink">변동성 · 낙폭 · 추세</h2>
        </div>
        <div className={`rounded-xl px-4 py-2.5 text-right ${tone.bg}`}>
          <p className={`text-display font-extrabold tabular leading-none ${tone.color}`}>
            {risk.risk_score}
          </p>
          <p className={`mt-1 text-xs font-bold ${tone.color}`}>{tone.label}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-2">
        {risk.metrics.map((metric) => (
          <div key={metric.name} className="rounded-xl bg-surface px-3.5 py-2.5">
            <p className="text-xs font-medium text-muted">{metric.name}</p>
            <p className="mt-1 text-sm font-bold text-ink tabular">{String(metric.value)}</p>
          </div>
        ))}
      </div>

      {risk.reasons?.length ? (
        <div className="mt-5 border-t border-line pt-4">
          <ul className="space-y-1.5 text-sm leading-6 text-sub">
            {risk.reasons.slice(0, 4).map((reason) => (
              <li key={reason} className="flex gap-2">
                <span className="text-warn">·</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
