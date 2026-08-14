import { Newspaper } from "lucide-react";
import type { NewsSentiment } from "@/lib/types";

/**
 * 뉴스 감성 카드 (제목 키워드 사전 기반).
 * 긍정(빨강) / 부정(파랑) — 한국 컨벤션.
 */
export default function NewsSentimentCard({ news }: { news: NewsSentiment }) {
  const score = news.sentiment_score;
  const color = score >= 60 ? "#F04452" : score <= 40 ? "#3182F6" : "#8B95A1";

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">뉴스 감성</p>
          <h2 className="mt-0.5 flex items-center gap-1.5 text-heading text-ink">
            <Newspaper size={18} className="text-muted" />
            최근 뉴스 분위기
          </h2>
        </div>
        <span className="chip" style={{ background: `${color}1A`, color }}>
          {news.label}
        </span>
      </div>

      {/* 점수 바 */}
      <div className="mb-4">
        <div className="mb-1 flex items-baseline justify-between text-xs">
          <span className="font-medium text-down">부정 {news.negative_count}</span>
          <span className="font-bold tabular" style={{ color }}>
            {score.toFixed(0)} / 100
          </span>
          <span className="font-medium text-up">긍정 {news.positive_count}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface">
          <div
            className="h-2 rounded-full transition-all duration-500"
            style={{ width: `${score}%`, background: color }}
          />
        </div>
      </div>

      {/* 헤드라인 */}
      <ul className="space-y-1.5">
        {news.headlines.map((h, i) => (
          <li key={i} className="flex items-start gap-2 text-xs leading-5">
            <span
              className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold tabular ${
                h.score > 0
                  ? "bg-up/15 text-up"
                  : h.score < 0
                    ? "bg-down/15 text-down"
                    : "bg-surface text-muted"
              }`}
            >
              {h.score > 0 ? "+" : ""}
              {h.score}
            </span>
            <span className="text-sub line-clamp-1">{h.title}</span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-[11px] leading-5 text-muted">
        최근 뉴스 제목 {news.total}건을 금융 키워드 사전으로 분석. 제목 기반이라 문맥은 반영 못
        합니다.
      </p>
    </div>
  );
}
