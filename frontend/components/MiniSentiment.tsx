import type { MarketSentiment } from "@/lib/types";

/** 상단바용 소형 공포·탐욕 표시. */
export default function MiniSentiment({ sentiment }: { sentiment: MarketSentiment | null }) {
  if (!sentiment) return null;
  const s = Math.max(0, Math.min(100, sentiment.score));
  const color =
    s <= 24
      ? "#3182F6"
      : s <= 44
        ? "#84B6FC"
        : s <= 55
          ? "#8B95A1"
          : s <= 74
            ? "#FF7B82"
            : "#F04452";
  return (
    <div
      className="hidden items-center gap-2 rounded-xl bg-surface px-3 py-1.5 sm:flex"
      title="시장 공포·탐욕 지수"
    >
      <span className="text-[10px] font-bold text-muted">심리</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-bg">
        <div className="h-1.5 rounded-full" style={{ width: `${s}%`, background: color }} />
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
