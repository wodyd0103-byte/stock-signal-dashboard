import { arcColor, textColor } from "@/lib/sentimentColor";
import type { MarketSentiment } from "@/lib/types";

/** 상단바용 소형 공포·탐욕 표시. */
export default function MiniSentiment({ sentiment }: { sentiment: MarketSentiment | null }) {
  if (!sentiment) return null;
  const s = Math.max(0, Math.min(100, sentiment.score));
  const bar = arcColor(s);
  const color = textColor(s);
  return (
    <div
      className="hidden items-center gap-2 rounded-xl bg-surface px-3 py-1.5 sm:flex"
      title="시장 공포·탐욕 지수"
    >
      <span className="text-[10px] font-bold text-muted">심리</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-bg">
        <div className="h-1.5 rounded-full" style={{ width: `${s}%`, background: bar }} />
      </div>
      <span className="text-sm font-extrabold tabular" style={{ color }}>
        {s}
      </span>
      <span className="text-[10px] font-bold" style={{ color }}>
        {sentiment.label}
      </span>
    </div>
  );
}
