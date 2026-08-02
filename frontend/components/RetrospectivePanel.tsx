"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Target } from "lucide-react";
import { evaluateRetro, fetchRetroSummary } from "@/lib/api";
import type { RetroSummary } from "@/lib/types";

/** 회고 패널 — 내 추천이 실제로 맞았나. 측정 인프라. */
export default function RetrospectivePanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<RetroSummary | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setData(await fetchRetroSummary());
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  }

  async function reEvaluate() {
    setLoading(true);
    try {
      setData(await evaluateRetro());
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !data) void load();
  }

  return (
    <section className="card">
      <button type="button" onClick={toggle} className="flex w-full items-center justify-between">
        <div className="flex items-center gap-2 text-left">
          <Target size={18} className="text-up" />
          <div>
            <p className="text-xs font-semibold text-muted">회고</p>
            <h2 className="mt-0.5 text-heading text-ink">내 추천, 실제로 맞았나?</h2>
          </div>
        </div>
        {open ? <ChevronUp size={18} className="text-muted" /> : <ChevronDown size={18} className="text-muted" />}
      </button>

      {open ? (
        <div className="mt-4 space-y-4">
          {loading && !data ? (
            <div className="h-24 animate-pulse rounded-xl bg-surface" />
          ) : data ? (
            <>
              {/* 핵심 지표 */}
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                <Stat label="적중률" value={data.hit_rate != null ? `${(data.hit_rate * 100).toFixed(0)}%` : "-"} tone={data.hit_rate != null && data.hit_rate >= 0.5 ? "up" : "down"} />
                <Stat label="평균 수익" value={data.avg_return != null ? `${data.avg_return >= 0 ? "+" : ""}${data.avg_return}%` : "-"} tone={data.avg_return != null && data.avg_return >= 0 ? "up" : "down"} />
                <Stat label="평가완료" value={`${data.evaluated}건`} tone="ink" />
                <Stat label="대기중" value={`${data.open}건`} tone="sub" />
              </div>

              {data.evaluated === 0 ? (
                <p className="rounded-xl bg-surface px-4 py-3 text-sm text-sub">
                  아직 평가된 추천이 없습니다. 매수 신호 종목이 기록되고 5거래일 경과 후 자동 채점됩니다.
                </p>
              ) : null}

              {/* 신호별 */}
              {data.by_signal.length ? (
                <div>
                  <p className="mb-2 text-xs font-bold text-muted">신호별 성과</p>
                  <div className="space-y-1">
                    {data.by_signal.map((s) => (
                      <div key={s.signal} className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2 text-sm">
                        <span className="w-24 font-bold text-ink">{s.signal}</span>
                        <span className="text-muted">{s.count}건</span>
                        <span className="ml-auto font-bold text-ink tabular">적중 {(s.hit_rate * 100).toFixed(0)}%</span>
                        <span className={`w-16 text-right font-bold tabular ${s.avg_return >= 0 ? "text-up" : "text-down"}`}>
                          {s.avg_return >= 0 ? "+" : ""}{s.avg_return}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* 최근 기록 */}
              {data.recent.length ? (
                <div>
                  <p className="mb-2 text-xs font-bold text-muted">최근 추천</p>
                  <div className="max-h-64 space-y-1 overflow-y-auto">
                    {data.recent.map((r) => {
                      const evaluated = r.status === "evaluated" && r.return_pct != null;
                      const up = (r.return_pct ?? 0) >= 0;
                      return (
                        <div key={r.id} className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs hover:bg-surface">
                          <span className="w-28 truncate font-bold text-ink">{r.name || r.ticker}</span>
                          <span className="rounded bg-up/15 px-1.5 py-0.5 text-[10px] font-bold text-up">{r.signal}</span>
                          <span className="text-muted tabular">{new Date(r.recommended_at).toLocaleDateString("ko-KR")}</span>
                          <span className="ml-auto tabular text-muted">
                            {evaluated ? (
                              <span className={`font-bold ${up ? "text-up" : "text-down"}`}>{up ? "+" : ""}{r.return_pct}%</span>
                            ) : (
                              <span className="text-faint">대기 ({r.horizon_days}일)</span>
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              <button type="button" onClick={() => void reEvaluate()} className="btn-ghost text-xs">지금 채점</button>
            </>
          ) : (
            <p className="text-sm text-muted">데이터 없음.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: "up" | "down" | "ink" | "sub" }) {
  const cls = { up: "text-up", down: "text-down", ink: "text-ink", sub: "text-sub" }[tone];
  return (
    <div className="card-surface">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className={`mt-1 text-xl font-extrabold tabular ${cls}`}>{value}</p>
    </div>
  );
}
