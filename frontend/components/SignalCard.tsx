import type { Signal, SignalScore } from "@/lib/types";

const signalStyle: Record<Signal, { bg: string; text: string; emoji: string }> = {
  "STRONG BUY": { bg: "bg-upStrong text-white", text: "강력 매수", emoji: "🚀" },
  BUY: { bg: "bg-upStrong text-white", text: "매수", emoji: "📈" },
  "WEAK BUY": { bg: "bg-up/15 text-up", text: "약매수", emoji: "↗" },
  HOLD: { bg: "bg-surface text-sub", text: "관망", emoji: "→" },
  "WEAK SELL": { bg: "bg-down/15 text-down", text: "약매도", emoji: "↘" },
  SELL: { bg: "bg-downStrong text-white", text: "매도", emoji: "📉" },
  "STRONG SELL": { bg: "bg-downStrong text-white", text: "강력 매도", emoji: "⚠" },
};

function ScoreBar({
  label,
  value,
  tone,
  zone,
}: {
  label: string;
  value: number;
  tone: string;
  zone?: string;
}) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-sm font-medium text-sub">{label}</span>
        <span className="text-sm font-bold text-ink tabular">
          {value}점{zone ? <span className="ml-1.5 text-muted font-medium">· {zone}</span> : null}
        </span>
      </div>
      <div className="h-2 rounded-full bg-surface">
        <div
          className={`h-2 rounded-full ${tone} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

export default function SignalCard({ signal }: { signal: SignalScore }) {
  const mlProbability =
    signal.ml_up_probability == null ? null : Math.round(signal.ml_up_probability * 100);
  const style = signalStyle[signal.signal];

  return (
    <section className="card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-muted">종합 신호</p>
          <h2 className="mt-0.5 text-heading text-ink">{style.text}</h2>
          <p className="mt-1 text-xs text-muted">절대 점수 · 시장 국면 · ML 확률 반영</p>
        </div>
        <span className={`chip text-sm px-3.5 py-1.5 ${style.bg}`}>
          <span>{style.emoji}</span>
          <span>{signal.signal}</span>
        </span>
      </div>

      <div className="mt-6 space-y-4">
        <ScoreBar
          label="최종 매수 점수"
          value={signal.final_buy_score ?? signal.buy_score}
          zone={signal.buy_score_zone}
          tone="bg-up"
        />
        <ScoreBar
          label="최종 매도 점수"
          value={signal.final_sell_score ?? signal.sell_score}
          zone={signal.sell_score_zone}
          tone="bg-down"
        />
        <ScoreBar
          label="리스크 점수"
          value={signal.risk_score}
          zone={signal.risk_score_zone}
          tone="bg-warn"
        />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-2">
        <Tile label="원 매수" value={`${signal.raw_buy_score ?? signal.buy_score}점`} />
        <Tile label="원 매도" value={`${signal.raw_sell_score ?? signal.sell_score}점`} />
        <Tile label="시장 국면" value={signal.market_regime ?? "-"} />
        <Tile
          label="ML 상승확률"
          value={mlProbability == null ? "데이터 부족" : `${mlProbability}%`}
          highlight={mlProbability != null && mlProbability >= 60}
        />
        <Tile
          label="상대 강도"
          value={
            signal.relative_strength_score == null
              ? "-"
              : `${signal.relative_strength_score.toFixed(2)}%`
          }
        />
        <Tile
          label="유동성"
          value={signal.liquidity_score == null ? "-" : `${signal.liquidity_score.toFixed(0)}점`}
        />
      </div>

      <div className="mt-5 rounded-xl bg-surface p-4">
        <p className="text-sm font-bold text-ink">판정: {signal.score_zone}</p>
        <p className="mt-1 text-sm leading-6 text-sub">{signal.signal_description}</p>
      </div>

      {signal.score_adjustments?.length ? (
        <div className="mt-5">
          <h3 className="text-sm font-bold text-ink">점수 보정 내역</h3>
          <ul className="mt-2 space-y-1.5 text-sm leading-6 text-sub">
            {signal.score_adjustments.slice(0, 5).map((reason) => (
              <li key={reason} className="flex gap-2">
                <span className="text-toss">·</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-5 border-t border-line pt-5">
        <h3 className="text-sm font-bold text-ink">
          {signal.signal === "HOLD" ? "HOLD 판단 이유" : "판단 이유"}
        </h3>
        <ul className="mt-2 space-y-1.5 text-sm leading-6 text-sub">
          {(signal.signal === "HOLD" && signal.hold_reasons?.length
            ? signal.hold_reasons
            : signal.reasons
          ).map((reason) => (
            <li key={reason} className="flex gap-2">
              <span className="text-toss">·</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Tile({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      className={`rounded-xl px-3.5 py-2.5 transition-colors ${highlight ? "bg-toss-50" : "bg-surface"}`}
    >
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className={`mt-0.5 text-sm font-bold tabular ${highlight ? "text-toss-600" : "text-ink"}`}>
        {value}
      </p>
    </div>
  );
}
