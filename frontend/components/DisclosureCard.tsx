import { AlertTriangle, FileText } from "lucide-react";
import type { DisclosureInfo } from "@/lib/types";

const catColor: Record<string, string> = {
  실적: "bg-toss-50 text-toss-600",
  자금조달: "bg-down/15 text-down",
  자사주: "bg-up/15 text-up",
  계약: "bg-up/15 text-up",
  배당: "bg-up/15 text-up",
  구조: "bg-warnBg text-warn",
  지분: "bg-surface text-sub",
  기타: "bg-surface text-muted",
};

/** 공시 카드 — 최근 공시 + 카테고리 태깅. 중요 공시/희석 이벤트 강조. */
export default function DisclosureCard({ disc }: { disc: DisclosureInfo }) {
  // 중요 공시 우선, 그다음 최신
  const sorted = [...disc.items].sort((a, b) => Number(b.important) - Number(a.important));
  const shown = sorted.slice(0, 6);

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">공시</p>
          <h2 className="mt-0.5 flex items-center gap-1.5 text-heading text-ink">
            <FileText size={18} className="text-muted" />
            최근 공시 ({disc.important_count} 중요)
          </h2>
        </div>
        {disc.has_dilution ? (
          <span className="chip bg-down/15 text-down">
            <AlertTriangle size={12} />
            희석 우려
          </span>
        ) : null}
      </div>

      {shown.length === 0 ? (
        <p className="rounded-xl bg-surface px-4 py-3 text-sm text-muted">최근 공시 없음.</p>
      ) : (
        <ul className="space-y-1.5">
          {shown.map((it, i) => (
            <li key={i} className="flex items-start gap-2 text-xs leading-5">
              <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${catColor[it.category] ?? catColor["기타"]}`}>
                {it.category}
              </span>
              <span className="flex-1 text-sub line-clamp-1">{it.title}</span>
              <span className="shrink-0 text-[10px] text-muted tabular">{it.datetime.slice(5, 10)}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-[11px] leading-5 text-muted">
        네이버 공시 제목 기반 키워드 분류. 상세는 증권사/DART에서 확인하세요.
      </p>
    </div>
  );
}
