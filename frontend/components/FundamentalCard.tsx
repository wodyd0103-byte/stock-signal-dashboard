import { Landmark } from "lucide-react";
import type { Fundamental } from "@/lib/types";

/** 재무/밸류에이션 카드 — PER/PBR/ROE/배당/52주 위치. */
export default function FundamentalCard({ f }: { f: Fundamental }) {
  const color = f.score >= 65 ? "#F04452" : f.score <= 35 ? "#3182F6" : "#8B95A1";
  const tiles: { label: string; value: string }[] = [
    { label: "PER", value: f.per != null ? `${f.per.toFixed(1)}배` : "-" },
    { label: "PBR", value: f.pbr != null ? `${f.pbr.toFixed(2)}배` : "-" },
    { label: "ROE(추정)", value: f.roe_est != null ? `${f.roe_est.toFixed(1)}%` : "-" },
    {
      label: "배당수익률",
      value: f.dividend_yield != null ? `${f.dividend_yield.toFixed(2)}%` : "-",
    },
    { label: "EPS", value: f.eps != null ? f.eps.toLocaleString() : "-" },
    { label: "52주 위치", value: f.pos_52w != null ? `${f.pos_52w.toFixed(0)}%` : "-" },
  ];

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">재무 · 밸류에이션</p>
          <h2 className="mt-0.5 flex items-center gap-1.5 text-heading text-ink">
            <Landmark size={18} className="text-muted" />
            펀더멘털
          </h2>
        </div>
        <span className="chip" style={{ background: `${color}1A`, color }}>
          {f.score >= 65 ? "저평가 우호" : f.score <= 35 ? "밸류 부담" : "중립"}{" "}
          {f.score.toFixed(0)}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-xl bg-surface px-3 py-2.5">
            <p className="text-[11px] font-medium text-muted">{t.label}</p>
            <p className="mt-0.5 text-sm font-bold text-ink tabular">{t.value}</p>
          </div>
        ))}
      </div>

      <p className="mt-3 text-[11px] leading-5 text-muted">
        네이버 제공 지표. ROE는 PBR/PER 근사치. 밸류에이션 참고용.
      </p>
    </div>
  );
}
