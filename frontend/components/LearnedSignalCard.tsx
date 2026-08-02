import { Cpu } from "lucide-react";
import type { LearnedSignal } from "@/lib/types";

/** IC 가중 학습 신호 — 손튜닝 점수와 별개, 데이터가 가중치 결정. */
export default function LearnedSignalCard({ ls }: { ls: LearnedSignal }) {
  const s = ls.score;
  const color = s >= 60 ? "#F04452" : s <= 40 ? "#3182F6" : "#8B95A1";

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">학습 기반 신호</p>
          <h2 className="mt-0.5 flex items-center gap-1.5 text-heading text-ink">
            <Cpu size={18} className="text-toss" />
            IC 가중 factor
          </h2>
        </div>
        <span className="chip" style={{ background: `${color}1A`, color }}>{ls.label}</span>
      </div>

      <div className="mb-3 flex items-baseline gap-2">
        <p className="text-display font-extrabold tabular leading-none" style={{ color }}>{s.toFixed(0)}</p>
        <span className="text-xs font-medium text-muted">/ 100 · factor {ls.used_factors}개 채택</span>
      </div>

      {ls.contributions.length ? (
        <div className="space-y-1">
          {ls.contributions.map((c) => {
            const pos = c.contrib >= 0;
            return (
              <div key={c.factor} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-surface">
                <span className="w-28 truncate font-bold text-ink">{c.label}</span>
                <span className="text-muted tabular">IC {c.ic >= 0 ? "+" : ""}{c.ic}</span>
                <span className="ml-auto tabular text-muted">z {c.z >= 0 ? "+" : ""}{c.z}</span>
                <span className={`w-14 text-right font-bold tabular ${pos ? "text-up" : "text-down"}`}>
                  {pos ? "+" : ""}{c.contrib}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="rounded-xl bg-surface px-3 py-2 text-xs text-muted">유효 factor 없음 (IC 미달).</p>
      )}

      <p className="mt-3 text-[11px] leading-5 text-muted">{ls.note}</p>
    </div>
  );
}
