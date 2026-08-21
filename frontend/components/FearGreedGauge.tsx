import { arcColor, textColor } from "@/lib/sentimentColor";
import type { MarketSentiment } from "@/lib/types";

/**
 * 공포·탐욕 지수 반원 게이지 (CNN Fear & Greed 스타일).
 * 0 = 극도 공포 (파랑/하락), 100 = 극도 탐욕 (빨강/상승).
 */
export default function FearGreedGauge({ sentiment }: { sentiment: MarketSentiment }) {
  const score = Math.max(0, Math.min(100, sentiment.score));

  // 반원: 180도(왼쪽, 0점) → 0도(오른쪽, 100점)
  const angle = 180 - (score / 100) * 180;
  const rad = (angle * Math.PI) / 180;
  const cx = 130;
  const cy = 130;
  const r = 100;
  const needleX = cx + r * 0.82 * Math.cos(rad);
  const needleY = cy - r * 0.82 * Math.sin(rad);

  // 숫자와 칩은 글씨라 대비 토큰을, 아크와 막대는 계조를 쓴다.
  const color = textColor(score);

  // 5구간 아크 (공포 → 탐욕)
  const segments = [
    { from: 0, to: 24, color: "#3182F6" }, // 극도 공포 (파랑)
    { from: 24, to: 44, color: "#84B6FC" }, // 공포
    { from: 44, to: 56, color: "#B0B8C1" }, // 중립 (회색)
    { from: 56, to: 75, color: "#FF7B82" }, // 탐욕
    { from: 75, to: 100, color: "#F04452" }, // 극도 탐욕 (빨강)
  ];

  return (
    <div className="card">
      <div className="mb-2 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">시장 심리</p>
          <h2 className="mt-0.5 text-heading text-ink">공포 · 탐욕 지수</h2>
        </div>
        <span className="chip text-sm px-3 py-1" style={{ background: `${color}1A`, color }}>
          {sentiment.label}
        </span>
      </div>

      <div className="flex flex-col items-center">
        <svg viewBox="0 0 260 150" className="w-full max-w-[280px]">
          {/* 배경 아크 세그먼트 */}
          {segments.map((seg, i) => (
            <path
              key={i}
              d={arcPath(cx, cy, r, seg.from, seg.to)}
              fill="none"
              stroke={seg.color}
              strokeWidth={16}
              strokeLinecap="butt"
              opacity={0.85}
            />
          ))}

          {/* 바늘 */}
          <line
            x1={cx}
            y1={cy}
            x2={needleX}
            y2={needleY}
            stroke="rgb(var(--c-ink))"
            strokeWidth={3}
            strokeLinecap="round"
          />
          <circle cx={cx} cy={cy} r={8} fill="rgb(var(--c-ink))" />
          <circle cx={cx} cy={cy} r={3.5} fill="rgb(var(--c-card))" />

          {/* 라벨 */}
          <text x={28} y={145} fontSize={9} fill="rgb(var(--c-muted))" fontWeight={700}>
            공포
          </text>
          <text x={210} y={145} fontSize={9} fill="rgb(var(--c-muted))" fontWeight={700}>
            탐욕
          </text>
        </svg>

        <div className="-mt-6 text-center">
          <p className="text-display font-extrabold tabular leading-none" style={{ color }}>
            {score}
          </p>
          <p className="mt-1 text-xs font-medium text-muted">/ 100</p>
        </div>
      </div>

      {/* 구성 요소 */}
      <div className="mt-4 space-y-1.5">
        {sentiment.components.map((c) => (
          <div key={c.name} className="flex items-center gap-2">
            <span className="w-40 shrink-0 truncate text-xs font-medium text-sub">{c.name}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface">
              <div
                className="h-1.5 rounded-full"
                style={{ width: `${c.score}%`, background: arcColor(c.score) }}
              />
            </div>
            <span className="w-8 text-right text-xs font-bold text-ink tabular">
              {Math.round(c.score)}
            </span>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-muted">
        VIX · KOSPI 변동성 · 추세 · 모멘텀 · 환율 변동성을 종합한 자체 지수입니다.
        {sentiment.risk_on ? " 현재 위험선호(risk-on)." : " 현재 위험회피(risk-off)."}
      </p>
    </div>
  );
}

/** 점수 from→to (0~100)를 반원 아크 path로. 0=왼쪽(180°), 100=오른쪽(0°). */
function arcPath(cx: number, cy: number, r: number, from: number, to: number): string {
  const a0 = (180 - (from / 100) * 180) * (Math.PI / 180);
  const a1 = (180 - (to / 100) * 180) * (Math.PI / 180);
  const x0 = cx + r * Math.cos(a0);
  const y0 = cy - r * Math.sin(a0);
  const x1 = cx + r * Math.cos(a1);
  const y1 = cy - r * Math.sin(a1);
  const largeArc = to - from > 50 ? 1 : 0;
  return `M ${x0} ${y0} A ${r} ${r} 0 ${largeArc} 1 ${x1} ${y1}`;
}
