"use client";

import { useState } from "react";
import { Flame, RefreshCcw, TrendingUp } from "lucide-react";
import { useBuySignals, useSurgeScan } from "@/hooks/queries";
import type { Signal } from "@/lib/types";

type Tab = "buy" | "surge";

const signalChip: Record<Signal, string> = {
  "STRONG BUY": "bg-up text-white",
  BUY: "bg-up text-white",
  "WEAK BUY": "bg-up/15 text-up",
  HOLD: "bg-surface text-sub",
  "WEAK SELL": "bg-down/15 text-down",
  SELL: "bg-down text-white",
  "STRONG SELL": "bg-down text-white",
};

export default function DiscoveryRail({
  onSelect,
  selected,
}: {
  onSelect: (t: string) => void;
  selected?: string;
}) {
  const [tab, setTab] = useState<Tab>("buy");

  // 각 탭은 열려 있을 때만 요청한다. 훅이 응답을 들고 있으므로 탭을 오갈 때
  // 다시 부르지 않는다 — 예전에 목록을 컴포넌트 state에 쌓아두던 것과 같은
  // 결과이고, 늦게 온 응답이 다른 탭 화면을 덮어쓰는 문제는 사라졌다.
  const buySignals = useBuySignals(tab === "buy");
  const surgeScan = useSurgeScan(tab === "surge");
  const active = tab === "buy" ? buySignals : surgeScan;

  const buy = buySignals.data ?? [];
  const surge = surgeScan.data ?? [];
  const loading = active.loading;
  const error = active.error;

  return (
    <div className="card flex h-full flex-col p-3">
      {/* 탭 */}
      <div className="mb-2 flex items-center gap-1 rounded-xl bg-surface p-1">
        <TabBtn
          active={tab === "buy"}
          onClick={() => setTab("buy")}
          icon={<TrendingUp size={14} />}
        >
          매수 신호
        </TabBtn>
        <TabBtn active={tab === "surge"} onClick={() => setTab("surge")} icon={<Flame size={14} />}>
          급등 탐색
        </TabBtn>
        <button
          type="button"
          onClick={active.refetch}
          className="ml-auto rounded-lg p-2 text-muted hover:bg-bg hover:text-ink"
          title="새로고침"
        >
          <RefreshCcw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {error ? <p className="px-2 py-3 text-xs text-down">{error}</p> : null}

      <div className="flex-1 space-y-1 overflow-y-auto">
        {loading && (tab === "buy" ? buy : surge).length === 0 ? (
          <SkeletonRows />
        ) : tab === "buy" ? (
          buy.length ? (
            buy.map((it) => (
              <Row
                key={it.ticker}
                active={selected === it.ticker}
                onClick={() => onSelect(it.ticker)}
                name={it.name}
                ticker={it.ticker}
                changeRate={it.change_rate}
                right={
                  <span className={`chip text-[10px] px-2 py-0.5 ${signalChip[it.signal]}`}>
                    {it.signal}
                  </span>
                }
              />
            ))
          ) : (
            <Empty text="신호 종목 없음" />
          )
        ) : surge.length ? (
          surge.map((it) => {
            const pct = Math.round(it.surge_probability * 100);
            const strong = it.surge_probability >= 0.6;
            return (
              <Row
                key={it.ticker}
                active={selected === it.ticker}
                onClick={() => onSelect(it.ticker)}
                name={it.name}
                ticker={it.ticker}
                changeRate={it.change_rate}
                right={
                  <span
                    className={`text-sm font-extrabold tabular ${strong ? "text-up" : "text-sub"}`}
                  >
                    {pct}%
                  </span>
                }
              />
            );
          })
        ) : (
          <Empty text="급등 후보 없음" />
        )}
      </div>
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex h-8 items-center gap-1 rounded-lg px-2.5 text-xs font-bold transition-colors ${active ? "bg-bg text-ink shadow-card" : "text-muted hover:text-sub"}`}
    >
      {icon}
      {children}
    </button>
  );
}

function Row({
  active,
  onClick,
  name,
  ticker,
  changeRate,
  right,
}: {
  active: boolean;
  onClick: () => void;
  name: string;
  ticker: string;
  changeRate: number;
  right: React.ReactNode;
}) {
  const up = changeRate >= 0;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-colors ${active ? "bg-toss-50 ring-1 ring-toss/30" : "hover:bg-surface"}`}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-ink">{name}</p>
        <p className="text-[10px] text-muted">
          {ticker} ·{" "}
          <span className={up ? "text-up" : "text-down"}>
            {up ? "+" : ""}
            {changeRate.toFixed(2)}%
          </span>
        </p>
      </div>
      {right}
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="px-2 py-6 text-center text-xs text-muted">{text}</p>;
}

function SkeletonRows() {
  return (
    <div className="space-y-1">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="h-12 animate-pulse rounded-xl bg-surface" />
      ))}
    </div>
  );
}
