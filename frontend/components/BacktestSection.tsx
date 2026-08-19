"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Play } from "lucide-react";
import BacktestChart from "@/components/BacktestChart";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse, BacktestStrategy, Period } from "@/lib/types";

const strategyOptions: Array<{ value: BacktestStrategy; label: string }> = [
  { value: "absolute_score_strategy", label: "절대 점수" },
  { value: "percentile_rank_strategy", label: "상대 순위" },
  { value: "ml_probability_strategy", label: "ML 확률" },
  { value: "regime_adjusted_strategy", label: "국면 보정" },
];

export default function BacktestSection({ ticker, period }: { ticker: string; period: Period }) {
  const [open, setOpen] = useState(false);
  const [strategy, setStrategy] = useState<BacktestStrategy>("regime_adjusted_strategy");
  const [capital, setCapital] = useState(10_000_000);
  const [result, setResult] = useState<BacktestResponse | null>(null);

  // 실행 버튼을 눌러야 도는 계산이라 조회 훅이 아니라 액션 훅을 쓴다.
  const backtest = useAsyncAction(fetchBacktest, { fallbackMessage: "백테스트 실패" });
  const { pending: loading, error } = backtest;

  async function run() {
    const res = await backtest.run(ticker, period, capital, strategy);
    if (res) setResult(res);
  }

  return (
    <section className="card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between"
      >
        <div className="text-left">
          <p className="text-xs font-semibold text-muted">백테스트</p>
          <h2 className="mt-0.5 text-heading text-ink">전략 검증 (다음 거래일 시가 체결)</h2>
        </div>
        {open ? (
          <ChevronUp size={18} className="text-muted" />
        ) : (
          <ChevronDown size={18} className="text-muted" />
        )}
      </button>

      {open ? (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex w-44 flex-col gap-1">
              <span className="text-xs font-bold text-muted">전략</span>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as BacktestStrategy)}
                className="h-11 rounded-xl bg-surface px-3 text-sm font-bold text-ink outline-none focus:bg-bg focus:ring-2 focus:ring-toss/50"
              >
                {strategyOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex w-44 flex-col gap-1">
              <span className="text-xs font-bold text-muted">초기 자본</span>
              <input
                type="number"
                value={capital}
                min={100000}
                step={100000}
                onChange={(e) => setCapital(Number(e.target.value))}
                className="h-11 rounded-xl bg-surface px-3 text-sm font-bold text-ink tabular outline-none focus:bg-bg focus:ring-2 focus:ring-toss/50"
              />
            </label>
            <button
              type="button"
              onClick={() => void run()}
              disabled={loading}
              className="inline-flex h-11 items-center gap-1.5 rounded-xl bg-toss px-5 text-sm font-bold text-white hover:bg-toss-600 disabled:bg-toss-300"
            >
              {loading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Play size={16} />
              )}
              실행
            </button>
          </div>

          {error ? (
            <div role="alert" className="rounded-card bg-down/10 px-4 py-3 text-sm text-down">
              {error}
            </div>
          ) : null}

          {result ? (
            <>
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                <Metric
                  label="총 수익률"
                  value={`${result.total_return >= 0 ? "+" : ""}${result.total_return.toFixed(2)}%`}
                  tone={result.total_return >= 0 ? "up" : "down"}
                />
                <Metric
                  label="보유 전략"
                  value={`${result.buy_and_hold_return >= 0 ? "+" : ""}${result.buy_and_hold_return.toFixed(2)}%`}
                  tone={result.buy_and_hold_return >= 0 ? "up" : "down"}
                />
                <Metric label="MDD" value={`${result.max_drawdown.toFixed(2)}%`} tone="warn" />
                <Metric label="승률" value={`${result.win_rate.toFixed(1)}%`} tone="ink" />
              </div>
              <BacktestChart data={result.chart} />
              <p className="text-xs leading-5 text-muted">{result.note}</p>
            </>
          ) : (
            <p className="text-sm text-muted">
              {loading ? "계산 중..." : "전략과 자본을 정하고 실행하세요."}
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "up" | "down" | "warn" | "ink";
}) {
  const cls = { up: "text-up", down: "text-down", warn: "text-warn", ink: "text-ink" }[tone];
  return (
    <div className="card-surface">
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className={`mt-1 text-lg font-extrabold tabular ${cls}`}>{value}</p>
    </div>
  );
}
