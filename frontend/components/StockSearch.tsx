"use client";

import { FormEvent, useEffect, useState } from "react";
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

  useEffect(() => { setTicker(defaultTicker); }, [defaultTicker]);
  useEffect(() => { setPeriod(defaultPeriod); }, [defaultPeriod]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = ticker.trim();
    if (value) onSearch(value.toUpperCase(), period);
  }

  return (
    <form onSubmit={handleSubmit} className="card flex items-center gap-2.5 p-2.5">
      <div className="flex flex-1 items-center gap-2 rounded-xl bg-surface px-4 transition-all focus-within:bg-bg focus-within:ring-2 focus-within:ring-toss/50">
        <Search size={18} className="text-muted shrink-0" />
        <input
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          className="h-12 flex-1 bg-transparent text-base font-semibold text-ink placeholder:text-faint placeholder:font-normal outline-none"
          placeholder="종목명 또는 티커 검색  (AAPL, 005930, 삼성전자)"
        />
      </div>

      <div className="flex h-12 items-center rounded-xl bg-surface p-1">
        {periods.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            className={`h-10 rounded-lg px-3 text-sm font-bold transition-colors ${
              period === item.value
                ? "bg-bg text-ink shadow-card"
                : "text-muted hover:text-sub"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="inline-flex h-12 min-w-28 items-center justify-center gap-1.5 rounded-xl bg-toss px-5 text-base font-bold text-white transition-colors hover:bg-toss-600 disabled:cursor-not-allowed disabled:bg-toss-300"
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
