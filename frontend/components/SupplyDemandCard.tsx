import { Building2, Globe, Layers } from "lucide-react";
import type { SectorStrength, SupplyDemand } from "@/lib/types";

/**
 * 외국인/기관 수급 카드. 한국시장 alpha 최강 factor.
 * 순매수(빨강) / 순매도(파랑) — 한국 컨벤션.
 */
export default function SupplyDemandCard({
  sd,
  sector,
}: {
  sd: SupplyDemand;
  sector?: SectorStrength | null;
}) {
  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <p className="text-xs font-semibold text-muted">수급 (외국인 · 기관)</p>
          <h2 className="mt-0.5 text-heading text-ink">매매 주체 흐름</h2>
        </div>
        <div className="flex items-center gap-2">
          {sd.foreign_hold_ratio != null ? (
            <span className="chip bg-surface text-sub" title="외국인 보유비율">
              외국인 {sd.foreign_hold_ratio.toFixed(1)}%
            </span>
          ) : null}
          <span className={`chip ${sd.buying ? "bg-up/15 text-up" : "bg-down/15 text-down"}`}>
            {sd.buying ? "순매수 우위" : "순매도 우위"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <FlowTile icon={<Globe size={14} />} label="외국인 5일" value={sd.foreign_5d} />
        <FlowTile icon={<Building2 size={14} />} label="기관 5일" value={sd.inst_5d} />
        <FlowTile icon={<Globe size={14} />} label="외국인 20일" value={sd.foreign_20d} muted />
        <FlowTile icon={<Building2 size={14} />} label="기관 20일" value={sd.inst_20d} muted />
      </div>

      {/* 수급 점수 바 */}
      <div className="mt-4">
        <div className="mb-1 flex items-baseline justify-between text-xs">
          <span className="font-medium text-sub">수급 점수</span>
          <span className="font-bold text-ink tabular">
            {sd.korean_flow_score.toFixed(0)} / 100
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${sd.korean_flow_score >= 50 ? "bg-up" : "bg-down"}`}
            style={{ width: `${sd.korean_flow_score}%` }}
          />
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-sub">{sd.summary}</p>

      {/* 업종 상대강도 */}
      {sector ? (
        <div className="mt-3 rounded-xl bg-surface px-3.5 py-2.5">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-1.5 text-xs font-bold text-sub">
              <Layers size={13} />
              업종 상대강도
            </p>
            <span
              className={`text-sm font-bold tabular ${sector.sector_rs >= 0 ? "text-up" : "text-down"}`}
            >
              {sector.sector_rs >= 0 ? "+" : ""}
              {sector.sector_rs.toFixed(1)}%p
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-bg">
            <div
              className={`h-1.5 rounded-full ${sector.score >= 50 ? "bg-up" : "bg-down"}`}
              style={{ width: `${sector.percentile}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] leading-4 text-muted">{sector.summary}</p>
        </div>
      ) : null}
    </div>
  );
}

function FlowTile({
  icon,
  label,
  value,
  muted,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  muted?: boolean;
}) {
  const up = value >= 0;
  return (
    <div className="rounded-xl bg-surface px-3 py-2.5">
      <p className="flex items-center gap-1 text-xs font-medium text-muted">
        {icon}
        {label}
      </p>
      {/* 약한 수급은 예전에 opacity-70 으로 흐리게 했는데, 색이 AA 를 지켜도
          투명도가 대비를 그만큼 깎아 결과가 미달이 된다. 색 토큰으로 표현한다. */}
      <p
        className={`mt-1 text-sm font-bold tabular ${muted ? "text-muted" : up ? "text-up" : "text-down"}`}
      >
        {up ? "+" : ""}
        {value.toLocaleString()}
        <span className="ml-1 text-[10px] font-medium text-muted">주</span>
      </p>
    </div>
  );
}
