"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowDownCircle, ArrowUpCircle, Briefcase, Link2, Plus, RefreshCcw, Scale, SlidersHorizontal, Sparkles, Trash2 } from "lucide-react";
import { addHolding, deleteHolding, fetchOptimize, fetchPortfolioAnalysis, fetchRebalance } from "@/lib/api";
import type { HoldingAnalysis, OptimizeResult, PortfolioReport, RebalancePlan } from "@/lib/types";

type Strategy = "equal" | "signal" | "risk_parity";
const STRAT_LABEL: Record<Strategy, string> = { equal: "균등", signal: "신호 가중", risk_parity: "리스크 역가중" };
type OptMethod = "max_sharpe" | "min_variance";
const OPT_LABEL: Record<OptMethod, string> = { max_sharpe: "최대 샤프", min_variance: "최소 분산" };

const signalChip: Record<string, string> = {
  "STRONG BUY": "bg-up text-white",
  BUY: "bg-up text-white",
  "WEAK BUY": "bg-up/15 text-up",
  HOLD: "bg-surface2 text-sub",
  "WEAK SELL": "bg-down/15 text-down",
  SELL: "bg-down text-white",
  "STRONG SELL": "bg-down text-white",
};

export default function PortfolioPanel({ onSelect }: { onSelect?: (t: string) => void }) {
  const [report, setReport] = useState<PortfolioReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("");
  const [avg, setAvg] = useState("");

  // 리밸런싱
  const [cash, setCash] = useState("");
  const [buffer, setBuffer] = useState("0");
  const [strategy, setStrategy] = useState<Strategy>("signal");
  const [plan, setPlan] = useState<RebalancePlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);

  // 수동 목표비중
  const [manualMode, setManualMode] = useState(false);
  const [manualW, setManualW] = useState<Record<string, string>>({});

  // 최적화 (Markowitz)
  const [optMethod, setOptMethod] = useState<OptMethod>("max_sharpe");
  const [opt, setOpt] = useState<OptimizeResult | null>(null);
  const [optLoading, setOptLoading] = useState(false);

  function toggleManual() {
    setManualMode((on) => {
      if (!on && report) {
        // 켤 때 현재 비중으로 프리필
        const seed: Record<string, string> = {};
        report.holdings.filter((h) => !h.error).forEach((h) => { seed[h.ticker] = h.weight.toFixed(0); });
        setManualW(seed);
      }
      return !on;
    });
  }

  const manualSum = Object.values(manualW).reduce((s, v) => s + (Number(v) || 0), 0);

  async function runRebalance() {
    setPlanLoading(true);
    try {
      const weights = manualMode
        ? Object.entries(manualW).filter(([, v]) => Number(v) > 0).map(([t, v]) => `${t}:${v}`).join(",")
        : undefined;
      setPlan(await fetchRebalance({ cash: Number(cash) || 0, strategy, maxWeight: 35, cashBuffer: Number(buffer) || 0, weights }));
    } catch {
      /* noop */
    } finally {
      setPlanLoading(false);
    }
  }

  async function runOptimize() {
    setOptLoading(true);
    try {
      setOpt(await fetchOptimize({ method: optMethod, maxWeight: 40 }));
    } catch {
      /* noop */
    } finally {
      setOptLoading(false);
    }
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchPortfolioAnalysis());
    } catch (e) {
      setError(e instanceof Error ? e.message : "포트폴리오 분석 실패");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    const q = Number(qty), a = Number(avg);
    if (!t || !(q > 0) || !(a > 0)) {
      setError("종목·수량·평단을 올바르게 입력하세요.");
      return;
    }
    try {
      await addHolding({ ticker: t, quantity: q, avg_price: a });
      setTicker(""); setQty(""); setAvg("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "추가 실패");
    }
  }

  async function remove(t: string) {
    try { await deleteHolding(t); await load(); } catch { /* noop */ }
  }

  const pnlUp = (report?.total_pnl ?? 0) >= 0;

  return (
    <section className="card">
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Briefcase size={18} className="text-toss" />
          <div>
            <p className="text-xs font-semibold text-muted">포트폴리오 설계사</p>
            <h2 className="mt-0.5 text-heading text-ink">내 보유 종목 진단</h2>
          </div>
        </div>
        <button type="button" onClick={() => void load()} className="btn-ghost">
          <RefreshCcw size={15} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* 입력 폼 */}
      <form onSubmit={submit} className="mb-4 grid grid-cols-[1.4fr_1fr_1.2fr_auto] gap-2">
        <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="종목 (005930)"
          className="h-11 rounded-xl bg-surface px-3 text-sm font-semibold text-ink placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50" />
        <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="수량" inputMode="decimal"
          className="h-11 rounded-xl bg-surface px-3 text-sm font-semibold text-ink tabular placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50" />
        <input value={avg} onChange={(e) => setAvg(e.target.value)} placeholder="평단가" inputMode="decimal"
          className="h-11 rounded-xl bg-surface px-3 text-sm font-semibold text-ink tabular placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50" />
        <button type="submit" className="inline-flex h-11 items-center gap-1 rounded-xl bg-toss px-4 text-sm font-bold text-white hover:bg-toss-600">
          <Plus size={16} />추가
        </button>
      </form>

      {error ? <div className="mb-3 rounded-xl bg-down/10 px-3 py-2 text-xs text-down">{error}</div> : null}

      {!report || report.holdings.length === 0 ? (
        <p className="rounded-xl bg-surface px-4 py-6 text-center text-sm text-muted">
          보유 종목을 추가하면 손익·신호·집중도·조언을 보여드립니다.
        </p>
      ) : (
        <>
          {/* 요약 카드 */}
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            <Stat label="평가금액" value={`${Math.round(report.total_value).toLocaleString()}원`} tone="ink" />
            <Stat label="총 손익" value={`${pnlUp ? "+" : ""}${Math.round(report.total_pnl).toLocaleString()}`} sub={`${report.total_pnl_pct >= 0 ? "+" : ""}${report.total_pnl_pct}%`} tone={pnlUp ? "up" : "down"} />
            <Stat label="집중도 / 최대비중" value={`${report.top_weight.toFixed(0)}%`} sub={`HHI ${report.concentration_hhi}`} tone={report.top_weight >= 40 ? "warn" : "sub"} />
            <Stat label="가중 리스크" value={`${report.weighted_risk.toFixed(0)}`} tone={report.weighted_risk >= 65 ? "warn" : "sub"} />
          </div>

          {/* 상관 분산 진단 */}
          {report.high_corr_pairs?.length ? (
            <div className="mt-3 rounded-xl bg-warnBg px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <Link2 size={14} className="text-warn" />
                <p className="text-xs font-bold text-warn">분산 주의 · 평균 상관 {report.avg_corr}</p>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {report.high_corr_pairs.map((p, i) => (
                  <span key={i} className="chip text-[11px]" style={{ background: "#F0445222", color: "#F04452" }}>
                    {p.a}·{p.b} {p.corr}
                  </span>
                ))}
              </div>
              <p className="mt-1.5 text-[10px] leading-4 text-warn/80">고상관 종목은 동반 등락 → 종목 수 대비 실제 분산효과 낮음.</p>
            </div>
          ) : null}

          {/* 보유 테이블 */}
          <div className="mt-4 space-y-1">
            {report.holdings.map((h) => (
              <HoldingRow key={h.ticker} h={h} onSelect={onSelect} onRemove={() => void remove(h.ticker)} />
            ))}
          </div>

          {/* 조언 */}
          {report.advice.length ? (
            <div className="mt-4 rounded-xl bg-surface p-4">
              <p className="mb-2 text-xs font-bold text-muted">설계사 조언</p>
              <ul className="space-y-1.5">
                {report.advice.map((a, i) => (
                  <li key={i} className="text-xs leading-5 text-sub">{a}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* 리밸런싱 계산기 */}
          <div className="mt-4 rounded-xl border border-line p-4">
            <div className="mb-3 flex items-center gap-2">
              <Scale size={16} className="text-toss" />
              <p className="text-sm font-bold text-ink">리밸런싱 계산기</p>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-bold text-muted">보유 현금(선택)</span>
                <input value={cash} onChange={(e) => setCash(e.target.value)} placeholder="0" inputMode="decimal"
                  className="h-10 w-28 rounded-xl bg-surface px-3 text-sm font-semibold text-ink tabular placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50" />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-bold text-muted">현금버퍼 %</span>
                <input value={buffer} onChange={(e) => setBuffer(e.target.value)} placeholder="0" inputMode="decimal"
                  className="h-10 w-20 rounded-xl bg-surface px-3 text-sm font-semibold text-ink tabular placeholder:text-faint outline-none focus:bg-card focus:ring-2 focus:ring-toss/50" />
              </label>
              <div className="flex h-10 items-center rounded-xl bg-surface p-1">
                {(["equal", "signal", "risk_parity"] as Strategy[]).map((s) => (
                  <button key={s} type="button" onClick={() => setStrategy(s)}
                    className={`h-8 rounded-lg px-2.5 text-xs font-bold transition-colors ${strategy === s ? "bg-card text-ink shadow-card" : "text-muted hover:text-sub"}`}>
                    {STRAT_LABEL[s]}
                  </button>
                ))}
              </div>
              <button type="button" onClick={toggleManual}
                className={`inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-xs font-bold transition-colors ${manualMode ? "bg-toss/15 text-toss" : "bg-surface text-muted hover:text-sub"}`}>
                <SlidersHorizontal size={14} />
                수동 비중
              </button>
              <button type="button" onClick={() => void runRebalance()}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-toss px-4 text-sm font-bold text-white hover:bg-toss-600">
                {planLoading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : <Scale size={15} />}
                계산
              </button>
            </div>

            {manualMode ? (
              <div className="mt-3 rounded-xl bg-surface p-3">
                <p className="mb-2 text-[11px] font-bold text-muted">목표비중 직접 입력 (%) · 합계는 자동 정규화</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {report.holdings.filter((h) => !h.error).map((h) => (
                    <label key={h.ticker} className="flex items-center gap-1.5">
                      <span className="w-16 truncate text-xs font-bold text-ink">{h.name}</span>
                      <input
                        value={manualW[h.ticker] ?? ""}
                        onChange={(e) => setManualW((m) => ({ ...m, [h.ticker]: e.target.value }))}
                        inputMode="decimal" placeholder="0"
                        className="h-9 w-14 rounded-lg bg-card px-2 text-sm font-semibold text-ink tabular outline-none focus:ring-2 focus:ring-toss/50"
                      />
                      <span className="text-xs text-faint">%</span>
                    </label>
                  ))}
                </div>
                <p className="mt-2 text-[11px] text-muted">입력 합계 {manualSum.toFixed(0)}% → 1.0으로 정규화되어 적용됩니다.</p>
              </div>
            ) : null}

            {plan && !plan.error ? (
              <div className="mt-3 space-y-1">
                <p className="text-[11px] text-muted">
                  투자가능 {plan.investable.toLocaleString()}원 · {plan.strategy === "custom" ? "수동 비중" : (STRAT_LABEL[plan.strategy as Strategy] ?? plan.strategy)} · 종목당 최대 {plan.max_weight}%
                </p>
                {plan.trades.map((t) => {
                  const isBuy = t.action === "buy";
                  const isSell = t.action === "sell";
                  return (
                    <div key={t.ticker} className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs hover:bg-surface">
                      <span className="w-24 truncate font-bold text-ink">{t.name}</span>
                      <span className="text-muted tabular">{t.current_weight}%→{t.target_weight}%</span>
                      <span className="ml-auto flex items-center gap-1 font-bold tabular">
                        {isBuy ? <ArrowUpCircle size={13} className="text-up" /> : isSell ? <ArrowDownCircle size={13} className="text-down" /> : null}
                        <span className={isBuy ? "text-up" : isSell ? "text-down" : "text-faint"}>
                          {t.action === "hold" ? "유지" : `${isBuy ? "매수" : "매도"} ${Math.abs(t.delta_shares)}주`}
                        </span>
                      </span>
                    </div>
                  );
                })}
                <div className="mt-1 flex justify-between border-t border-line pt-2 text-xs font-bold">
                  <span className="text-up">매수 {plan.buy_total.toLocaleString()}원</span>
                  <span className="text-down">매도 {plan.sell_total.toLocaleString()}원</span>
                </div>
                <div className="flex justify-between text-[11px] text-muted tabular">
                  <span>예상 비용 {plan.est_cost_total.toLocaleString()}원 (수수료+매도세)</span>
                  <span>잔여현금 {plan.residual_cash.toLocaleString()}원</span>
                </div>
                <p className="mt-1 text-[10px] leading-4 text-muted">{plan.note}</p>
              </div>
            ) : plan?.error ? (
              <p className="mt-3 text-xs text-down">{plan.error}</p>
            ) : null}
          </div>

          {/* 최적 비중 (Markowitz) */}
          <div className="mt-4 rounded-xl border border-line p-4">
            <div className="mb-1 flex items-center gap-2">
              <Sparkles size={16} className="text-toss" />
              <p className="text-sm font-bold text-ink">최적 비중 (Markowitz)</p>
            </div>
            <p className="mb-3 text-[11px] text-muted">최근 1년 수익률·Ledoit-Wolf 수축 공분산 기반. 현재 보유 종목 한정.</p>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex h-10 items-center rounded-xl bg-surface p-1">
                {(["max_sharpe", "min_variance"] as OptMethod[]).map((m) => (
                  <button key={m} type="button" onClick={() => setOptMethod(m)}
                    className={`h-8 rounded-lg px-2.5 text-xs font-bold transition-colors ${optMethod === m ? "bg-card text-ink shadow-card" : "text-muted hover:text-sub"}`}>
                    {OPT_LABEL[m]}
                  </button>
                ))}
              </div>
              <button type="button" onClick={() => void runOptimize()}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-toss px-4 text-sm font-bold text-white hover:bg-toss-600">
                {optLoading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : <Sparkles size={15} />}
                계산
              </button>
            </div>

            {opt && !opt.error ? (
              <div className="mt-3 space-y-1.5">
                <div className="flex flex-wrap gap-2 text-[11px] font-bold">
                  <span className="chip bg-surface2 text-sub">기대수익 {opt.exp_return}%</span>
                  <span className="chip bg-surface2 text-sub">변동성 {opt.exp_vol}%</span>
                  <span className="chip" style={{ background: "#3182F622", color: "#3182F6" }}>샤프 {opt.sharpe}</span>
                </div>
                {Object.entries(opt.weights).sort((a, b) => b[1] - a[1]).map(([t, w]) => (
                  <div key={t} className="flex items-center gap-2 text-xs">
                    <span className="w-16 truncate font-bold text-ink">{t}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface">
                      <div className="h-full rounded-full bg-toss" style={{ width: `${Math.min(100, w * 100)}%` }} />
                    </div>
                    <span className="w-12 text-right font-bold tabular text-sub">{(w * 100).toFixed(1)}%</span>
                  </div>
                ))}
                <p className="mt-1 text-[10px] leading-4 text-muted">{opt.note}</p>
              </div>
            ) : opt?.error ? (
              <p className="mt-3 text-xs text-down">{opt.error}</p>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}

function HoldingRow({ h, onSelect, onRemove }: { h: HoldingAnalysis; onSelect?: (t: string) => void; onRemove: () => void }) {
  const up = h.pnl_pct >= 0;
  if (h.error) {
    return (
      <div className="flex items-center gap-2 rounded-xl bg-surface px-3 py-2.5 text-sm">
        <span className="font-bold text-ink">{h.name}</span>
        <span className="text-xs text-down">{h.error}</span>
        <button type="button" onClick={onRemove} className="ml-auto rounded-lg p-1.5 text-faint hover:text-down"><Trash2 size={14} /></button>
      </div>
    );
  }
  return (
    <div className="group flex items-center gap-2 rounded-xl px-3 py-2.5 transition-colors hover:bg-surface">
      <button type="button" onClick={() => onSelect?.(h.ticker)} className="flex flex-1 items-center gap-2 text-left">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="truncate text-sm font-bold text-ink">{h.name}</span>
            <span className={`chip text-[10px] px-1.5 py-0.5 ${signalChip[h.signal] ?? signalChip.HOLD}`}>{h.signal}</span>
          </div>
          <p className="text-[10px] text-muted tabular">{h.quantity}주 · 평단 {h.avg_price.toLocaleString()} · 비중 {h.weight.toFixed(0)}%</p>
        </div>
        <div className="text-right">
          <p className="text-sm font-bold text-ink tabular">{h.current_price.toLocaleString()}</p>
          <p className={`text-xs font-bold tabular ${up ? "text-up" : "text-down"}`}>{up ? "+" : ""}{h.pnl_pct.toFixed(1)}%</p>
        </div>
      </button>
      <button type="button" onClick={onRemove} className="rounded-lg p-1.5 text-faint opacity-0 transition-opacity hover:bg-down/10 hover:text-down group-hover:opacity-100"><Trash2 size={14} /></button>
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone: "up" | "down" | "warn" | "ink" | "sub" }) {
  const cls = { up: "text-up", down: "text-down", warn: "text-warn", ink: "text-ink", sub: "text-sub" }[tone];
  return (
    <div className="card-surface !p-3">
      <p className="text-[11px] font-semibold text-muted">{label}</p>
      <p className={`mt-0.5 text-lg font-extrabold tabular ${cls}`}>{value}</p>
      {sub ? <p className={`text-[11px] font-bold tabular ${cls}`}>{sub}</p> : null}
    </div>
  );
}
