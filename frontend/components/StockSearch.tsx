"use client";

import { FormEvent, useState } from "react";
import { Search } from "lucide-react";
import { periods } from "@/lib/api";
import type { Period } from "@/lib/types";

interface StockSearchProps {
  defaultTicker?: string;
  defaultPeriod?: Period;
  onSearch: (ticker: string, period: Period) => void;
  loading?: boolean;
}

export default function StockSearch({
  defaultTicker = "AAPL",
  defaultPeriod = "1y",
  onSearch,
  loading,
}: StockSearchProps) {
  const [ticker, setTicker] = useState(defaultTicker);
  const [period, setPeriod] = useState<Period>(defaultPeriod);

  // 부모가 다른 종목/기간을 확정하면 입력값도 따라가야 한다. 이펙트로 맞추면 한 번 더
  // 렌더된 뒤에 값이 바뀌므로, React가 권장하는 렌더 중 조정 방식을 쓴다.
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const [syncedTicker, setSyncedTicker] = useState(defaultTicker);
  if (syncedTicker !== defaultTicker) {
    setSyncedTicker(defaultTicker);
    setTicker(defaultTicker);
  }

  const [syncedPeriod, setSyncedPeriod] = useState<Period>(defaultPeriod);
  if (syncedPeriod !== defaultPeriod) {
    setSyncedPeriod(defaultPeriod);
    setPeriod(defaultPeriod);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = ticker.trim();
    if (value) onSearch(value.toUpperCase(), period);
  }

  return (
    // 좁은 화면에서는 입력이 한 줄을 다 쓰고, 기간 선택과 분석 버튼이 아랫줄로 내려간다.
    <form onSubmit={handleSubmit} className="card flex flex-wrap items-center gap-2.5 p-2.5">
      <div className="flex min-w-0 grow basis-full items-center gap-2 rounded-xl bg-surface px-4 transition-all focus-within:bg-bg focus-within:ring-2 focus-within:ring-toss/50 sm:basis-0">
        <Search size={18} className="text-muted shrink-0" />
        <input
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          className="h-12 flex-1 bg-transparent text-base font-semibold text-ink placeholder:text-faint placeholder:font-normal outline-none"
          placeholder="종목명 또는 티커 검색  (AAPL, 005930, 삼성전자)"
        />
      </div>

      <div className="flex h-12 min-w-0 grow items-center rounded-xl bg-surface p-1 sm:grow-0">
        {periods.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            className={`h-10 grow rounded-lg px-2 text-sm font-bold transition-colors sm:grow-0 sm:px-3 ${
              period === item.value ? "bg-bg text-ink shadow-card" : "text-muted hover:text-sub"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="inline-flex h-12 shrink-0 items-center justify-center gap-1.5 rounded-xl bg-toss px-4 text-base font-bold text-white transition-colors hover:bg-toss-600 disabled:cursor-not-allowed disabled:bg-toss-300 sm:min-w-28 sm:px-5"
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <Search size={18} />
        )}
        분석
      </button>
    </form>
  );
}
