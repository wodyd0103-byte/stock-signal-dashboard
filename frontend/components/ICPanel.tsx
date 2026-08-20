"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FlaskConical } from "lucide-react";
import { useFactorIC } from "@/hooks/queries";
import { useRadioGroup } from "@/hooks/useRadioGroup";
import type { FactorIC } from "@/lib/types";

const horizons = [3, 5, 10];

/** Factor IC 진단 패널 — 어느 신호가 실제 미래수익과 상관있나. 시장 전체(종목 무관). */
export default function ICPanel() {
  const [open, setOpen] = useState(false);
  const [horizon, setHorizon] = useState(5);
  const horizonGroup = useRadioGroup<number>({
    values: horizons,
    active: horizon,
    onChange: setHorizon,
    label: "예측 시계",
  });

  // 접혀 있는 동안에는 요청하지 않는다. 펴는 순간 처음 부르고, 시계를 바꾸면
  // 그 시계로 다시 부르되 이미 본 시계는 캐시에서 즉시 나온다.
  const { data: report, error, loading, refetch } = useFactorIC(horizon, open);

  return (
    <section className="card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between"
      >
        <div className="flex items-center gap-2 text-left">
          <FlaskConical size={18} className="text-toss" />
          <div>
            <p className="text-xs font-semibold text-muted">팩터 진단 (IC)</p>
            <h2 className="mt-0.5 text-heading text-ink">어느 신호가 실제로 먹히나?</h2>
          </div>
        </div>
        {open ? (
          <ChevronUp size={18} className="text-muted" />
        ) : (
          <ChevronDown size={18} className="text-muted" />
        )}
      </button>

      {open ? (
        <div className="mt-4 space-y-3">
          {/* horizon 토글 */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-muted">예측 시계</span>
            <div
              {...horizonGroup.groupProps}
              className="flex h-9 items-center rounded-xl bg-surface p-1"
            >
              {horizons.map((h) => (
                <button
                  key={h}
                  type="button"
                  {...horizonGroup.getRadioProps(h)}
                  className={`h-7 rounded-lg px-3 text-xs font-bold transition-colors ${horizon === h ? "bg-bg text-ink shadow-card" : "text-muted hover:text-sub"}`}
                >
                  {h}일
                </button>
              ))}
            </div>
            <button type="button" onClick={refetch} className="btn-ghost ml-auto text-xs">
              재계산
            </button>
          </div>

          {error ? (
            <div role="alert" className="rounded-card bg-down/10 px-4 py-3 text-sm text-down">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="space-y-1">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-10 animate-pulse rounded-xl bg-surface" />
              ))}
            </div>
          ) : report && report.factors.length ? (
            <>
              <div className="space-y-1">
                {report.factors.map((f) => (
                  <Row key={f.factor} f={f} />
                ))}
              </div>
              <p className="text-[11px] leading-5 text-muted">{report.note}</p>
              <p className="text-[11px] text-muted">
                유니버스 {report.universe_size}종목 · {report.horizon_days}일 시계 · 갱신{" "}
                {new Date(report.updated_at).toLocaleString("ko-KR")}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted">데이터 부족 — IC 계산 불가.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function Row({ f }: { f: FactorIC }) {
  // IC -0.06 ~ +0.06 범위를 막대로. 0 중심.
  const pct = Math.max(-100, Math.min(100, (f.ic / 0.06) * 100));
  const pos = f.ic >= 0;
  const verdictColor =
    f.verdict === "강함"
      ? "text-up"
      : f.verdict === "보통"
        ? "text-toss-600"
        : f.verdict === "약함"
          ? "text-sub"
          : "text-faint";

  return (
    <div className="flex items-center gap-3 rounded-xl px-3 py-2 transition-colors hover:bg-surface">
      <span className="w-32 shrink-0 truncate text-sm font-bold text-ink">{f.label}</span>

      {/* 중앙 0 기준 막대 */}
      <div className="relative h-2 flex-1 rounded-full bg-surface">
        <div className="absolute left-1/2 top-0 h-2 w-px bg-line" />
        <div
          className={`absolute top-0 h-2 rounded-full ${pos ? "bg-up" : "bg-down"}`}
          style={
            pos ? { left: "50%", width: `${pct / 2}%` } : { right: "50%", width: `${-pct / 2}%` }
          }
        />
      </div>

      <span
        className={`w-16 text-right text-xs font-bold tabular ${pos ? "text-up" : "text-down"}`}
      >
        {f.ic >= 0 ? "+" : ""}
        {f.ic.toFixed(4)}
      </span>
      <span className={`w-12 shrink-0 text-right text-[10px] font-bold ${verdictColor}`}>
        {f.verdict}
      </span>
    </div>
  );
}
