"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Repeat } from "lucide-react";
import { useSignalChanges } from "@/hooks/queries";
import type { SignalChangeRecord } from "@/lib/types";

const WINDOWS = [30, 90] as const;

/**
 * 신호 전환 이력 — 이 종목이 원래 자주 뒤집히나.
 *
 * 기록은 digest CLI(`python -m tools.digest`)가 남긴다. 화면에서 만드는 값이
 * 아니라서, CLI 를 한 번도 돌리지 않았으면 비어 있는 것이 정상이다.
 */
export default function SignalHistoryPanel() {
  const [open, setOpen] = useState(false);
  const [days, setDays] = useState<number>(30);

  // 접혀 있는 동안에는 요청하지 않는다.
  const { data, loading, error } = useSignalChanges(open, days);

  return (
    <section className="card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between"
      >
        <div className="flex items-center gap-2 text-left">
          <Repeat size={18} className="text-muted" />
          <div>
            <p className="text-xs font-semibold text-muted">신호 이력</p>
            <h2 className="mt-0.5 text-heading text-ink">이 종목, 원래 자주 뒤집히나?</h2>
          </div>
        </div>
        {open ? (
          <ChevronUp size={18} className="text-muted" />
        ) : (
          <ChevronDown size={18} className="text-muted" />
        )}
      </button>

      {open ? (
        <div className="mt-4 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted">기간</span>
            {WINDOWS.map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setDays(w)}
                aria-pressed={days === w}
                className={`rounded-lg px-2.5 py-1 text-xs font-bold ${
                  days === w ? "bg-ink text-bg" : "bg-surface text-muted hover:text-ink"
                }`}
              >
                {w}일
              </button>
            ))}
          </div>

          {loading && !data ? (
            <div className="h-24 animate-pulse rounded-xl bg-surface" />
          ) : error && !data ? (
            <p className="text-sm text-muted">{error}</p>
          ) : data && data.total > 0 ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Stat label="전환 기록" value={`${data.total}건`} />
                <Stat label="종목 수" value={`${data.tickers}개`} />
              </div>

              {data.flips.length ? (
                <div>
                  <p className="mb-2 text-xs font-bold text-muted">
                    자주 뒤집힌 종목 — 등급이 바뀐 횟수만 셉니다
                  </p>
                  <div className="space-y-1">
                    {data.flips.map((flip) => (
                      <div
                        key={flip.ticker}
                        className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2 text-sm"
                      >
                        <span className="truncate font-bold text-ink">
                          {flip.name || flip.ticker}
                        </span>
                        <span className="text-xs text-muted tabular">{flip.ticker}</span>
                        <span className="ml-auto font-bold text-ink tabular">{flip.count}회</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="rounded-xl bg-surface px-4 py-3 text-sm text-sub">
                  {days}일 안에 두 번 이상 뒤집힌 종목은 없습니다.
                </p>
              )}

              {data.recent.length ? (
                <div>
                  <p className="mb-2 text-xs font-bold text-muted">최근 전환</p>
                  <div className="max-h-64 space-y-1 overflow-y-auto">
                    {data.recent.map((row) => (
                      <ChangeRow key={row.id} row={row} />
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="rounded-xl bg-surface px-4 py-3 text-sm text-sub">
              아직 기록된 전환이 없습니다. 이력은 일일 리포트 CLI(
              <code className="tabular">python -m tools.digest</code>)가 실행될 때마다 쌓입니다.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

const KIND_LABEL: Record<string, string> = { score: "매수점수", risk: "리스크" };

function ChangeRow({ row }: { row: SignalChangeRecord }) {
  const tone =
    row.direction === "up" ? "text-up" : row.direction === "down" ? "text-down" : "text-muted";
  const label = KIND_LABEL[row.kind];
  return (
    <div className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs hover:bg-surface">
      <span className="w-28 truncate font-bold text-ink">{row.name || row.ticker}</span>
      {label ? <span className="text-[10px] font-bold text-muted">{label}</span> : null}
      <span className={`font-bold ${row.kind === "signal" ? tone : "text-sub"}`}>
        {row.previous_signal
          ? `${row.previous_signal} → ${row.current_signal}`
          : `신규 ${row.current_signal}`}
      </span>
      <span className="ml-auto tabular text-muted">
        {new Date(row.recorded_at).toLocaleDateString("ko-KR")}
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card-surface">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="mt-1 text-xl font-extrabold text-ink tabular">{value}</p>
    </div>
  );
}
